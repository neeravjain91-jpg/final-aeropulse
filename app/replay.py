from __future__ import annotations

import math

from .degradation import estimate_degradation_horizon
from .navigation import SimulatedGPSSource, DEFAULT_MISSION_WAYPOINTS
from .risk import mission_risk
from .rul_service import RULService
from .simulator import inject_fault, mission_adjust


_RUL = RULService()
_GPS = SimulatedGPSSource()


def _dynamic_step(base: dict, index: int, steps: int) -> dict:
    data = dict(base)

    phase = 2.0 * math.pi * index / max(steps, 1)

    data["Engine_RPM"] *= (
        1.0 + 0.012 * math.sin(phase * 3.0)
    )

    data["Fuel_Flow"] *= (
        1.0 + 0.018 * math.sin(phase * 2.0 + 0.4)
    )

    for key, offset in [
        ("EGT1", 0.0),
        ("EGT2", 0.8),
        ("EGT3", 1.6),
    ]:
        data[key] *= (
            1.0
            + 0.006
            * math.sin(phase * 2.5 + offset)
        )

    data["Oil_Temp"] *= (
        1.0 + 0.004 * math.sin(phase)
    )

    data["MAP_Injector"] *= (
        1.0 + 0.008 * math.sin(phase * 1.5)
    )

    return data


def _replay_rul(
    health_history: list[float],
    fallback: dict,
    step_minutes: float,
    elapsed_hours: float = 0.0,
    stress: float = 1.0,
    tbo_hours: float = 1200.0,
    current_health: float = 100.0,
) -> dict:

    trend = estimate_degradation_horizon(
        health_history,
        step_minutes,
        max_horizon_hours=tbo_hours,
    )

    consumed_life = elapsed_hours * stress
    max_achievable = max(0.0, tbo_hours - consumed_life)

    if trend.get("rul_hours") is not None and trend.get("status") == "DEGRADING":
        confidence = float(trend.get("confidence", 0.75))
        horizon = float(trend["rul_hours"])
        spread = 0.25 * (1.0 - confidence) + 0.05
        bounded = max(0.0, min(max_achievable, horizon))

        return {
            "rul_hours": round(bounded, 2),
            "rul_lower_hours": max(0.0, round(bounded * (1.0 - spread), 2)),
            "rul_upper_hours": round(bounded * (1.0 + spread), 2),
            "rul_confidence": round(confidence, 2),
            "confidence": round(confidence, 2),
            "status": "ACTIVE_DEGRADATION",
            "degradation_rate_per_hour": round(float(trend.get("trend_per_hour", 0.5)), 3),
        }

    # If fallback is provided and has rul_hours, ensure elapsed hours are accounted for
    if fallback and fallback.get("rul_hours") is not None:
        fb_rul = float(fallback["rul_hours"])
        bounded = max(0.0, min(max_achievable, fb_rul))
        conf = float(fallback.get("rul_confidence", fallback.get("confidence", 0.75)))
        spread = 0.25 * (1.0 - conf) + 0.05
        return {
            **fallback,
            "rul_hours": round(bounded, 2),
            "rul_lower_hours": max(0.0, round(bounded * (1.0 - spread), 2)),
            "rul_upper_hours": round(bounded * (1.0 + spread), 2),
        }

    return fallback


def _trajectory_health(
    analysis: dict,
    fault_name: str,
    fault_severity: float,
) -> float:
    """
    Create a replay-specific health trajectory.

    The ML/twin health index remains the primary diagnostic signal.
    During an injected-fault replay, an explicit bounded degradation
    trajectory is added so that the RUL demonstrator receives a
    meaningful monotonic degradation signal.

    This is a software demonstrator mechanism, not a physical engine
    degradation model.
    """

    base_health = float(
        analysis.get(
            "health_index",
            0.0,
        )
    )

    base_health = max(
        0.0,
        min(
            100.0,
            base_health,
        ),
    )

    severity = max(
        0.0,
        min(
            1.0,
            float(fault_severity),
        ),
    )

    if fault_name == "none":
        return round(
            base_health,
            1,
        )

    # The diagnostic health index is already derived from observable
    # telemetry/physics evidence. Do not subtract the injected fault severity
    # again here: that would make replay health depend directly on the known
    # synthetic label and would double-count degradation.
    replay_health = base_health

    return round(
        max(
            0.0,
            min(
                100.0,
                replay_health,
            ),
        ),
        1,
    )


def run_replay(
    ai,
    base: dict,
    scenario: dict,
    steps: int = 48,
    step_minutes: float = 5.0,
    fault_onset_ratio: float = 0.35,
) -> dict:

    steps = max(
        12,
        min(
            int(steps),
            180,
        ),
    )

    step_minutes = max(
        0.5,
        min(
            float(step_minutes),
            60.0,
        ),
    )

    onset = max(
        0.0,
        min(
            0.95,
            float(fault_onset_ratio),
        ),
    )

    onset_step = int(
        steps * onset
    )

    target_severity = max(
        0.0,
        min(
            1.0,
            float(
                scenario.get(
                    "severity",
                    0.6,
                )
            ),
        ),
    )

    fault_name = str(
        scenario.get(
            "fault",
            "none",
        )
    )

    timeline = []

    health_history = []

    ai_warning_step = None

    reference_alarm_step = None

    custom_wps = scenario.get("waypoints")
    if custom_wps and len(custom_wps) >= 2:
        gps = SimulatedGPSSource(
            waypoints=custom_wps,
            ground_temp_c=float(scenario.get("ambient_c", 30.0)),
        )
    else:
        gps = _GPS

    for i in range(steps):

        point = _dynamic_step(
            base,
            i,
            steps,
        )

        ratio = i / max(1, steps - 1)
        uav_pos = gps.get_position(ratio)

        if scenario.get("simulation_mode") != "manual_override":
            step_alt = uav_pos.altitude_ft
            step_amb = uav_pos.ambient_c
            step_dur = max(0.5, gps.total_duration_min / 60.0)
        else:
            step_alt = float(scenario.get("altitude_ft", 3000))
            step_amb = float(scenario.get("ambient_c", 25))
            step_dur = float(scenario.get("duration_h", 4))

        point = mission_adjust(
            point,
            step_alt,
            step_amb,
            step_dur,
            bool(
                scenario.get(
                    "rapid_throttle",
                    False,
                )
            ),
        )

        fault_severity = 0.0

        if (
            fault_name != "none"
            and i >= onset_step
        ):

            progress = (
                i - onset_step + 1
            ) / max(
                1,
                steps - onset_step,
            )

            progress = max(
                0.0,
                min(
                    1.0,
                    progress,
                ),
            )

            fault_severity = (
                target_severity
                * progress
            )

            point = inject_fault(
                point,
                fault_name,
                fault_severity,
            )

            point["Degradation_Severity"] = max(
                float(
                    point.get(
                        "Degradation_Severity",
                        0.0,
                    )
                ),
                fault_severity,
            )

        analysis = ai.analyze(
            point,
            context=scenario,
        )

        risk = mission_risk(
            analysis,
            scenario,
        )

        anomaly_flag = bool(
            analysis.get(
                "anomaly_flag",
                False,
            )
        )

        health_warning = (
            analysis["health_state"]
            in {
                "Warning",
                "Critical",
            }
            and float(
                analysis["twin"]["residual_rms"]
            ) >= 1.0
        )

        reference_alarm = (
            float(
                analysis["twin"]["max_abs_z"]
            ) >= 3.0
        )

        intelligent_warning = (
            anomaly_flag
            or health_warning
            or float(
                analysis["twin"]["residual_rms"]
            ) >= 1.0
        )

        if (
            ai_warning_step is None
            and intelligent_warning
        ):
            ai_warning_step = i

        if (
            reference_alarm_step is None
            and reference_alarm
        ):
            reference_alarm_step = i

        # ---------------------------------------------------------
        # Replay-specific health trajectory
        # ---------------------------------------------------------

        replay_health = _trajectory_health(
            analysis=analysis,
            fault_name=fault_name,
            fault_severity=fault_severity,
        )

        health_history.append(
            replay_health
        )

        # ---------------------------------------------------------
        # Feature-based fallback RUL and dynamic trend estimation
        # ---------------------------------------------------------
        elapsed_hours = (i * step_minutes) / 60.0
        eid = scenario.get("engine_id", "Rotax-914-Turbo-115HP")
        tbo_hours = _RUL.get_engine_tbo(eid)
        stress = _RUL.calculate_mission_stress(scenario)

        fallback = _RUL.predict(
            point,
            context={
                "engine_id": eid,
                "elapsed_hours": elapsed_hours,
                "stress": stress,
                "mission_hours": float(scenario.get("duration_h", 4)),
                "ambient_c": float(scenario.get("ambient_c", 25)),
                "altitude_ft": float(scenario.get("altitude_ft", 3000)),
            },
        )

        rul = _replay_rul(
            health_history,
            fallback,
            step_minutes,
            elapsed_hours=elapsed_hours,
            stress=stress,
            tbo_hours=tbo_hours,
            current_health=replay_health,
        )

        timeline.append(
            {
                "step": i,

                "time_min": round(
                    i * step_minutes,
                    2,
                ),

                "health_state":
                    (
                        "Normal"
                        if replay_health >= 85
                        else "Watch"
                        if replay_health >= 65
                        else "Warning"
                        if replay_health >= 40
                        else "Critical"
                    ),

                "health_index":
                    replay_health,

                "ml_health_index":
                    analysis[
                        "health_index"
                    ],

                "anomaly_score":
                    analysis[
                        "anomaly_score"
                    ],

                "residual_rms": round(
                    float(
                        analysis["twin"][
                            "residual_rms"
                        ]
                    ),
                    3,
                ),

                "max_abs_z": round(
                    float(
                        analysis["twin"][
                            "max_abs_z"
                        ]
                    ),
                    3,
                ),

                "risk_score":
                    risk["score"],

                "risk_level":
                    risk["level"],

                "primary_fault": (
                    analysis[
                        "fault_candidates"
                    ][0]["name"]
                    if analysis[
                        "fault_candidates"
                    ]
                    else "None"
                ),

                "sensor_trust":
                    analysis[
                        "sensor_health"
                    ][
                        "overall_trust_score"
                    ],

                "rul": rul,

                "rul_hours":
                    rul.get("rul_hours"),

                "rul_lower_hours":
                    rul.get("rul_lower_hours"),

                "rul_upper_hours":
                    rul.get("rul_upper_hours"),

                "rul_confidence":
                    rul.get("rul_confidence", rul.get("confidence", 0.75)),

                "degradation_severity":
                    round(
                        float(
                            point.get(
                                "Degradation_Severity",
                                0.0,
                            )
                        ),
                        4,
                    ),

                "uav": uav_pos.to_dict(),
                "environment": uav_pos.environment or {},

                "telemetry": {
                    k: (
                        round(
                            float(v),
                            4,
                        )
                        if isinstance(
                            v,
                            (int, float),
                        )
                        else v
                    )
                    for k, v in point.items()
                },
            }
        )

    early = None

    if (
        ai_warning_step is not None
        and reference_alarm_step is not None
    ):
        early = round(
            (
                reference_alarm_step
                - ai_warning_step
            )
            * step_minutes,
            2,
        )

    print(
        "REPLAY HEALTH HISTORY:",
        [
            round(
                float(x),
                2,
            )
            for x in health_history
        ],
    )

    rul_method = estimate_degradation_horizon(
        health_history,
        step_minutes,
    )

    return {
        "timeline": timeline,

        "summary": {
            "steps": steps,

            "step_minutes":
                step_minutes,

            "fault_onset_step": (
                onset_step
                if fault_name != "none"
                else None
            ),

            "fault_onset_min": (
                round(
                    onset_step
                    * step_minutes,
                    2,
                )
                if fault_name != "none"
                else None
            ),

            "intelligent_warning_step":
                ai_warning_step,

            "intelligent_warning_min": (
                round(
                    ai_warning_step
                    * step_minutes,
                    2,
                )
                if ai_warning_step
                is not None
                else None
            ),

            "ai_warning_step":
                ai_warning_step,

            "ai_warning_min": (
                round(
                    ai_warning_step
                    * step_minutes,
                    2,
                )
                if ai_warning_step
                is not None
                else None
            ),

            "reference_alarm_step":
                reference_alarm_step,

            "reference_alarm_min": (
                round(
                    reference_alarm_step
                    * step_minutes,
                    2,
                )
                if reference_alarm_step
                is not None
                else None
            ),

            "early_warning_gain_min":
                early,

            "comparison_note":
                (
                    "The intelligent warning fuses "
                    "model/twin evidence; the reference "
                    "alarm is a 3-sigma single-parameter "
                    "Digital-Twin baseline. Neither is a "
                    "certified engine limit."
                ),

            "final_health_index":
                timeline[-1][
                    "health_index"
                ],

            "final_health_state":
                timeline[-1][
                    "health_state"
                ],

            "peak_risk_score":
                max(
                    x["risk_score"]
                    for x in timeline
                ),

            "initial_rul_hours":
                timeline[0][
                    "rul_hours"
                ],

            "final_rul_hours":
                timeline[-1][
                    "rul_hours"
                ],

            "rul_change_hours":
                round(
                    timeline[-1][
                        "rul_hours"
                    ]
                    - timeline[0][
                        "rul_hours"
                    ],
                    2,
                ),

            "rul_method_demonstrator":
                rul_method,

            "rul_note":
                (
                    "RUL preferentially follows the "
                    "observed replay health trajectory "
                    "when a finite trend estimate is "
                    "available; otherwise it falls back "
                    "to the feature-based methodology "
                    "model. This is not validated "
                    "run-to-failure RUL for a deployed "
                    "MALE-UAV engine."
                ),
        },

        "waypoints": [wp.to_dict() for wp in gps.waypoints],
        "planned_route": [[wp.latitude, wp.longitude] for wp in gps.waypoints],
        "home_base": gps.waypoints[0].to_dict(),
        "flight_plan_summary": gps.get_flight_plan_summary(),
    }