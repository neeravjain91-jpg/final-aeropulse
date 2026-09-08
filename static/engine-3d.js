/*
 * AeroPulse-X WebGL 3D Piston Engine Digital Twin & Interactive Simulator
 * ------------------------------------------------------------------------
 * High-definition, hardware-accelerated WebGL mechanical simulator for an
 * Inline 4-Cylinder, 4-Stroke Turbocharged Liquid-Cooled Aero-Piston Engine.
 *
 * Implements:
 * 1. Authoritative Crank Angle State theta in [0, 4*PI) (0 to 720 deg)
 *    - 0-180 deg   : INTAKE (Intake valve open, piston descending TDC -> BDC)
 *    - 180-360 deg : COMPRESSION (Both valves closed, piston ascending BDC -> TDC)
 *    - 360-540 deg : POWER / COMBUSTION (Spark at TDC 360 deg, power stroke TDC -> BDC)
 *    - 540-720 deg : EXHAUST (Exhaust valve open, piston ascending BDC -> TDC)
 * 2. Flat-plane Firing Order 1 - 3 - 4 - 2:
 *    - Cyl 1: theta
 *    - Cyl 2: (theta + 3*PI) % (4*PI)  [540 deg offset]
 *    - Cyl 3: (theta + 1*PI) % (4*PI)  [180 deg offset]
 *    - Cyl 4: (theta + 2*PI) % (4*PI)  [360 deg offset]
 * 3. Exact Slider-Crank Mathematics:
 *    y_piston(theta) = r * cos(theta) + sqrt(L^2 - (r * sin(theta))^2)
 *    phi_rod(theta) = -asin( (r * sin(theta)) / L )
 * 4. DOHC Valvetrain: Camshafts rotate at exactly 1/2 crank speed (theta_cam = 0.5 * theta)
 * 5. Dynamic Compressing Helical Valve Springs (physically compressed by cam lift)
 * 6. Synchronized 2D Canvases:
 *    - 2D Kinematic Vector Schematic with live formula x(theta)
 *    - Valve Timing & Piston Motion Diagram (0-720 deg) with live tracking cursor
 *    - P-V Indicator Diagram (Cylinder Pressure vs Volume) with live operating point
 * 7. Multi-Mode Shaders: Normal, X-Ray Crystal, Exploded Assembly, Thermal Heatmap, Vibration
 * 8. 3D Leader-Line Labels & Component Callouts
 */

(function () {
  'use strict';

  const DEG = Math.PI / 180;
  const RAD = 180 / Math.PI;
  const clamp = (v, min, max) => Math.max(min, Math.min(max, v));
  const lerp = (a, b, t) => a + (b - a) * t;

  // --- 4x4 Matrix Math Utilities ---
  function mat4Identity() {
    return new Float32Array([
      1, 0, 0, 0,
      0, 1, 0, 0,
      0, 0, 1, 0,
      0, 0, 0, 1
    ]);
  }

  function mat4Multiply(a, b) {
    const out = new Float32Array(16);
    for (let col = 0; col < 4; col += 1) {
      for (let row = 0; row < 4; row += 1) {
        let sum = 0;
        for (let k = 0; k < 4; k += 1) {
          sum += a[k * 4 + row] * b[col * 4 + k];
        }
        out[col * 4 + row] = sum;
      }
    }
    return out;
  }

  function mat4Translation(x, y, z) {
    const out = mat4Identity();
    out[12] = x;
    out[13] = y;
    out[14] = z;
    return out;
  }

  function mat4Scale(x, y, z) {
    const out = mat4Identity();
    out[0] = x;
    out[5] = y;
    out[10] = z;
    return out;
  }

  function mat4RotationX(angle) {
    const c = Math.cos(angle), s = Math.sin(angle);
    return new Float32Array([
      1, 0, 0, 0,
      0, c, s, 0,
      0, -s, c, 0,
      0, 0, 0, 1
    ]);
  }

  function mat4RotationY(angle) {
    const c = Math.cos(angle), s = Math.sin(angle);
    return new Float32Array([
      c, 0, -s, 0,
      0, 1, 0, 0,
      s, 0, c, 0,
      0, 0, 0, 1
    ]);
  }

  function mat4RotationZ(angle) {
    const c = Math.cos(angle), s = Math.sin(angle);
    return new Float32Array([
      c, s, 0, 0,
      -s, c, 0, 0,
      0, 0, 1, 0,
      0, 0, 0, 1
    ]);
  }

  function compose(position, rotation, scale) {
    let out = mat4Translation(position[0], position[1], position[2]);
    if (rotation[2] !== 0) out = mat4Multiply(out, mat4RotationZ(rotation[2]));
    if (rotation[1] !== 0) out = mat4Multiply(out, mat4RotationY(rotation[1]));
    if (rotation[0] !== 0) out = mat4Multiply(out, mat4RotationX(rotation[0]));
    return mat4Multiply(out, mat4Scale(scale[0], scale[1], scale[2]));
  }

  function mat4Perspective(fov, aspect, near, far) {
    const f = 1 / Math.tan(fov / 2);
    const nf = 1 / (near - far);
    const out = new Float32Array(16);
    out[0] = f / aspect;
    out[5] = f;
    out[10] = (far + near) * nf;
    out[11] = -1;
    out[14] = 2 * far * near * nf;
    return out;
  }

  function normalize(v) {
    const len = Math.hypot(v[0], v[1], v[2]) || 1;
    return [v[0] / len, v[1] / len, v[2] / len];
  }

  function cross(a, b) {
    return [
      a[1] * b[2] - a[2] * b[1],
      a[2] * b[0] - a[0] * b[2],
      a[0] * b[1] - a[1] * b[0]
    ];
  }

  function mat4LookAt(eye, target, up) {
    const z = normalize([eye[0] - target[0], eye[1] - target[1], eye[2] - target[2]]);
    const x = normalize(cross(up, z));
    const y = cross(z, x);
    return new Float32Array([
      x[0], y[0], z[0], 0,
      x[1], y[1], z[1], 0,
      x[2], y[2], z[2], 0,
      -(x[0] * eye[0] + x[1] * eye[1] + x[2] * eye[2]),
      -(y[0] * eye[0] + y[1] * eye[1] + y[2] * eye[2]),
      -(z[0] * eye[0] + z[1] * eye[1] + z[2] * eye[2]),
      1
    ]);
  }

  function transformPoint(matrix, point) {
    const x = point[0], y = point[1], z = point[2];
    const w = matrix[3] * x + matrix[7] * y + matrix[11] * z + matrix[15];
    return [
      (matrix[0] * x + matrix[4] * y + matrix[8] * z + matrix[12]) / w,
      (matrix[1] * x + matrix[5] * y + matrix[9] * z + matrix[13]) / w,
      (matrix[2] * x + matrix[6] * y + matrix[10] * z + matrix[14]) / w
    ];
  }

  // --- Color Helpers ---
  function hexColor(hex) {
    const val = Number.parseInt(hex.replace('#', ''), 16);
    return [((val >> 16) & 255) / 255, ((val >> 8) & 255) / 255, (val & 255) / 255];
  }

  function mixColor(a, b, t) {
    return [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)];
  }

  function thermalColor(value, low, high) {
    const t = clamp((value - low) / (high - low), 0, 1);
    if (t < 0.28) return mixColor(hexColor('#3fa66a'), hexColor('#62c87b'), t / 0.28);
    if (t < 0.60) return mixColor(hexColor('#62c87b'), hexColor('#e0b343'), (t - 0.28) / 0.32);
    if (t < 0.85) return mixColor(hexColor('#e0b343'), hexColor('#e85d3a'), (t - 0.60) / 0.25);
    return mixColor(hexColor('#e85d3a'), hexColor('#ff2b2b'), (t - 0.85) / 0.15);
  }

  // --- Procedural 3D Geometry Generators (CCW Front Winding) ---

  function makeCube() {
    const positions = [];
    const normals = [];
    const indices = [];
    const faces = [
      [[1, 0, 0], [[0.5, -0.5, -0.5], [0.5, 0.5, -0.5], [0.5, 0.5, 0.5], [0.5, -0.5, 0.5]]],
      [[-1, 0, 0], [[-0.5, -0.5, 0.5], [-0.5, 0.5, 0.5], [-0.5, 0.5, -0.5], [-0.5, -0.5, -0.5]]],
      [[0, 1, 0], [[-0.5, 0.5, -0.5], [-0.5, 0.5, 0.5], [0.5, 0.5, 0.5], [0.5, 0.5, -0.5]]],
      [[0, -1, 0], [[-0.5, -0.5, 0.5], [-0.5, -0.5, -0.5], [0.5, -0.5, -0.5], [0.5, -0.5, 0.5]]],
      [[0, 0, 1], [[-0.5, -0.5, 0.5], [0.5, -0.5, 0.5], [0.5, 0.5, 0.5], [-0.5, 0.5, 0.5]]],
      [[0, 0, -1], [[-0.5, -0.5, -0.5], [-0.5, 0.5, -0.5], [0.5, 0.5, -0.5], [0.5, -0.5, -0.5]]]
    ];
    faces.forEach(([norm, quad]) => {
      const baseIdx = positions.length / 3;
      quad.forEach(pt => {
        positions.push(...pt);
        normals.push(...norm);
      });
      indices.push(baseIdx, baseIdx + 1, baseIdx + 2, baseIdx, baseIdx + 2, baseIdx + 3);
    });
    return { positions, normals, indices };
  }

  function makeCylinder(segments = 24, radiusTop = 0.5, radiusBottom = 0.5, height = 1.0) {
    const positions = [];
    const normals = [];
    const indices = [];
    const halfH = height * 0.5;

    for (let i = 0; i <= segments; i += 1) {
      const u = i / segments;
      const theta = u * Math.PI * 2;
      const cosT = Math.cos(theta);
      const sinT = Math.sin(theta);
      positions.push(cosT * radiusTop, halfH, sinT * radiusTop);
      positions.push(cosT * radiusBottom, -halfH, sinT * radiusBottom);
      normals.push(cosT, 0, sinT);
      normals.push(cosT, 0, sinT);
    }
    for (let i = 0; i < segments; i += 1) {
      const i0 = i * 2;
      const i1 = i0 + 1;
      const i2 = i0 + 2;
      const i3 = i0 + 3;
      indices.push(i0, i2, i1, i1, i2, i3);
    }

    const topCenter = positions.length / 3;
    positions.push(0, halfH, 0);
    normals.push(0, 1, 0);
    for (let i = 0; i <= segments; i += 1) {
      const theta = (i / segments) * Math.PI * 2;
      positions.push(Math.cos(theta) * radiusTop, halfH, Math.sin(theta) * radiusTop);
      normals.push(0, 1, 0);
    }
    for (let i = 0; i < segments; i += 1) {
      indices.push(topCenter, topCenter + 2 + i, topCenter + 1 + i);
    }

    const bottomCenter = positions.length / 3;
    positions.push(0, -halfH, 0);
    normals.push(0, -1, 0);
    for (let i = 0; i <= segments; i += 1) {
      const theta = (i / segments) * Math.PI * 2;
      positions.push(Math.cos(theta) * radiusBottom, -halfH, Math.sin(theta) * radiusBottom);
      normals.push(0, -1, 0);
    }
    for (let i = 0; i < segments; i += 1) {
      indices.push(bottomCenter, bottomCenter + 1 + i, bottomCenter + 2 + i);
    }

    return { positions, normals, indices };
  }

  function makeCutawayCylinder(segments = 24, startAngle = Math.PI * 0.75, endAngle = Math.PI * 2.25, innerR = 0.44, outerR = 0.54, height = 1.0) {
    const positions = [];
    const normals = [];
    const indices = [];
    const halfH = height * 0.5;
    const segCount = Math.max(4, Math.round(segments * ((endAngle - startAngle) / (Math.PI * 2))));

    // Outer wall
    for (let i = 0; i <= segCount; i += 1) {
      const theta = startAngle + (i / segCount) * (endAngle - startAngle);
      const cosT = Math.cos(theta);
      const sinT = Math.sin(theta);
      positions.push(cosT * outerR, halfH, sinT * outerR);
      positions.push(cosT * outerR, -halfH, sinT * outerR);
      normals.push(cosT, 0, sinT);
      normals.push(cosT, 0, sinT);
    }
    for (let i = 0; i < segCount; i += 1) {
      const i0 = i * 2;
      indices.push(i0, i0 + 2, i0 + 1, i0 + 1, i0 + 2, i0 + 3);
    }

    // Inner wall
    const innerBase = positions.length / 3;
    for (let i = 0; i <= segCount; i += 1) {
      const theta = startAngle + (i / segCount) * (endAngle - startAngle);
      const cosT = Math.cos(theta);
      const sinT = Math.sin(theta);
      positions.push(cosT * innerR, halfH, sinT * innerR);
      positions.push(cosT * innerR, -halfH, sinT * innerR);
      normals.push(-cosT, 0, -sinT);
      normals.push(-cosT, 0, -sinT);
    }
    for (let i = 0; i < segCount; i += 1) {
      const i0 = innerBase + i * 2;
      indices.push(i0, i0 + 1, i0 + 2, i0 + 2, i0 + 1, i0 + 3);
    }

    // Cut face 1
    const cut1Base = positions.length / 3;
    const cosS = Math.cos(startAngle), sinS = Math.sin(startAngle);
    const nCut1 = [-sinS, 0, cosS];
    positions.push(cosS * innerR, halfH, sinS * innerR);
    positions.push(cosS * outerR, halfH, sinS * outerR);
    positions.push(cosS * outerR, -halfH, sinS * outerR);
    positions.push(cosS * innerR, -halfH, sinS * innerR);
    for (let k = 0; k < 4; k++) normals.push(...nCut1);
    indices.push(cut1Base, cut1Base + 3, cut1Base + 2, cut1Base, cut1Base + 2, cut1Base + 1);

    // Cut face 2
    const cut2Base = positions.length / 3;
    const cosE = Math.cos(endAngle), sinE = Math.sin(endAngle);
    const nCut2 = [sinE, 0, -cosE];
    positions.push(cosE * outerR, halfH, sinE * outerR);
    positions.push(cosE * innerR, halfH, sinE * innerR);
    positions.push(cosE * innerR, -halfH, sinE * innerR);
    positions.push(cosE * outerR, -halfH, sinE * outerR);
    for (let k = 0; k < 4; k++) normals.push(...nCut2);
    indices.push(cut2Base, cut2Base + 3, cut2Base + 2, cut2Base, cut2Base + 2, cut2Base + 1);

    return { positions, normals, indices };
  }

  function makeSphere(latBands = 14, lonBands = 20) {
    const positions = [];
    const normals = [];
    const indices = [];
    for (let lat = 0; lat <= latBands; lat += 1) {
      const theta = (lat * Math.PI) / latBands;
      const sinT = Math.sin(theta);
      const cosT = Math.cos(theta);
      for (let lon = 0; lon <= lonBands; lon += 1) {
        const phi = (lon * 2 * Math.PI) / lonBands;
        const x = Math.cos(phi) * sinT * 0.5;
        const y = cosT * 0.5;
        const z = Math.sin(phi) * sinT * 0.5;
        positions.push(x, y, z);
        normals.push(x * 2, y * 2, z * 2);
      }
    }
    for (let lat = 0; lat < latBands; lat += 1) {
      for (let lon = 0; lon < lonBands; lon += 1) {
        const first = lat * (lonBands + 1) + lon;
        const second = first + lonBands + 1;
        indices.push(first, first + 1, second, second, first + 1, second + 1);
      }
    }
    return { positions, normals, indices };
  }

  function makeTorus(radialSegments = 24, tubularSegments = 14, radius = 0.5, tube = 0.12) {
    const positions = [];
    const normals = [];
    const indices = [];
    for (let j = 0; j <= radialSegments; j += 1) {
      for (let i = 0; i <= tubularSegments; i += 1) {
        const u = (i / tubularSegments) * Math.PI * 2;
        const v = (j / radialSegments) * Math.PI * 2;
        const x = (radius + tube * Math.cos(v)) * Math.cos(u);
        const y = (radius + tube * Math.cos(v)) * Math.sin(u);
        const z = tube * Math.sin(v);
        positions.push(x, y, z);
        const cx = radius * Math.cos(u);
        const cy = radius * Math.sin(u);
        normals.push(x - cx, y - cy, z);
      }
    }
    for (let j = 1; j <= radialSegments; j += 1) {
      for (let i = 1; i <= tubularSegments; i += 1) {
        const a = (tubularSegments + 1) * j + i - 1;
        const b = (tubularSegments + 1) * (j - 1) + i - 1;
        const c = (tubularSegments + 1) * (j - 1) + i;
        const d = (tubularSegments + 1) * j + i;
        indices.push(a, b, d, b, c, d);
      }
    }
    return { positions, normals, indices };
  }

  function makeHelicalSpring(coils = 4.5, radius = 0.16, wireRadius = 0.032, height = 0.45) {
    const positions = [];
    const normals = [];
    const indices = [];
    const steps = 36;
    const ringSteps = 6;
    const totalTurns = coils * Math.PI * 2;

    for (let s = 0; s <= steps; s += 1) {
      const t = s / steps;
      const angle = t * totalTurns;
      const cx = Math.cos(angle) * radius;
      const cy = (t - 0.5) * height;
      const cz = Math.sin(angle) * radius;

      const tx = -Math.sin(angle) * radius;
      const ty = height / totalTurns;
      const tz = Math.cos(angle) * radius;
      const tang = normalize([tx, ty, tz]);
      const norm = normalize([cx, 0, cz]);
      const binorm = cross(tang, norm);

      for (let r = 0; r < ringSteps; r += 1) {
        const theta = (r / ringSteps) * Math.PI * 2;
        const cosR = Math.cos(theta) * wireRadius;
        const sinR = Math.sin(theta) * wireRadius;
        const px = cx + norm[0] * cosR + binorm[0] * sinR;
        const py = cy + norm[1] * cosR + binorm[1] * sinR;
        const pz = cz + norm[2] * cosR + binorm[2] * sinR;
        positions.push(px, py, pz);
        normals.push(norm[0] * cosR + binorm[0] * sinR, norm[1] * cosR + binorm[1] * sinR, norm[2] * cosR + binorm[2] * sinR);
      }
    }

    for (let s = 0; s < steps; s += 1) {
      for (let r = 0; r < ringSteps; r += 1) {
        const nextR = (r + 1) % ringSteps;
        const i0 = s * ringSteps + r;
        const i1 = (s + 1) * ringSteps + r;
        const i2 = (s + 1) * ringSteps + nextR;
        const i3 = s * ringSteps + nextR;
        indices.push(i0, i2, i1, i0, i3, i2);
      }
    }
    return { positions, normals, indices };
  }

  function makePiston() {
    const positions = [];
    const normals = [];
    const indices = [];
    const segs = 24;
    const r = 0.42;
    const h = 0.52;

    // Crown dish
    const centerIdx = positions.length / 3;
    positions.push(0, h * 0.5 - 0.035, 0);
    normals.push(0, 1, 0);
    for (let i = 0; i <= segs; i += 1) {
      const th = (i / segs) * Math.PI * 2;
      positions.push(Math.cos(th) * r, h * 0.5, Math.sin(th) * r);
      normals.push(0, 1, 0);
    }
    for (let i = 0; i < segs; i += 1) {
      indices.push(centerIdx, centerIdx + 2 + i, centerIdx + 1 + i);
    }

    // Skirt & Ring Lands
    const rings = [0.5, 0.42, 0.38, 0.30, 0.26, 0.18, 0.14, -0.5];
    const ringRadii = [r, r, r * 0.94, r * 0.94, r, r * 0.94, r * 0.94, r];

    for (let ringIdx = 0; ringIdx < rings.length; ringIdx += 1) {
      const ringY = rings[ringIdx] * (h * 0.5);
      const ringR = ringRadii[ringIdx];
      for (let i = 0; i <= segs; i += 1) {
        const th = (i / segs) * Math.PI * 2;
        const cosT = Math.cos(th);
        const sinT = Math.sin(th);
        positions.push(cosT * ringR, ringY, sinT * ringR);
        normals.push(cosT, 0, sinT);
      }
    }

    for (let ringIdx = 0; ringIdx < rings.length - 1; ringIdx += 1) {
      const base0 = (segs + 2) + ringIdx * (segs + 1);
      const base1 = (segs + 2) + (ringIdx + 1) * (segs + 1);
      for (let i = 0; i < segs; i += 1) {
        indices.push(base0 + i, base0 + i + 1, base1 + i, base1 + i, base0 + i + 1, base1 + i + 1);
      }
    }

    // Bottom cap
    const botCenter = positions.length / 3;
    positions.push(0, -h * 0.5, 0);
    normals.push(0, -1, 0);
    for (let i = 0; i <= segs; i += 1) {
      const th = (i / segs) * Math.PI * 2;
      positions.push(Math.cos(th) * r, -h * 0.5, Math.sin(th) * r);
      normals.push(0, -1, 0);
    }
    for (let i = 0; i < segs; i += 1) {
      indices.push(botCenter, botCenter + 1 + i, botCenter + 2 + i);
    }

    return { positions, normals, indices };
  }

  function makeConnectingRod() {
    const positions = [];
    const normals = [];
    const indices = [];

    function addBox(x, y, z, w, h, d) {
      const b = makeCube();
      const base = positions.length / 3;
      for (let i = 0; i < b.positions.length; i += 3) {
        positions.push(
          b.positions[i] * w + x,
          b.positions[i + 1] * h + y,
          b.positions[i + 2] * d + z
        );
        normals.push(b.normals[i], b.normals[i + 1], b.normals[i + 2]);
      }
      for (let i = 0; i < b.indices.length; i++) {
        indices.push(base + b.indices[i]);
      }
    }

    // Central I-Beam shank
    addBox(0, 0, 0, 0.08, 1.05, 0.04);
    addBox(0, 0, 0.045, 0.09, 1.05, 0.03);
    addBox(0, 0, -0.045, 0.09, 1.05, 0.03);

    // Big-end journal boss
    addBox(0, -0.55, 0, 0.16, 0.22, 0.18);
    // Small-end wrist pin boss
    addBox(0, 0.55, 0, 0.12, 0.16, 0.14);

    return { positions, normals, indices };
  }

  function makeCrankshaftWeb() {
    const positions = [];
    const normals = [];
    const indices = [];
    const segs = 12;
    const r = 0.52;
    const thick = 0.11;

    positions.push(0, 0, thick * 0.5);
    normals.push(0, 0, 1);
    positions.push(0, 0, -thick * 0.5);
    normals.push(0, 0, -1);

    const startA = Math.PI * 0.65;
    const endA = Math.PI * 1.35;

    for (let i = 0; i <= segs; i += 1) {
      const th = startA + (i / segs) * (endA - startA);
      const cosT = Math.cos(th) * r;
      const sinT = Math.sin(th) * r;
      positions.push(cosT, sinT, thick * 0.5);
      normals.push(0, 0, 1);
      positions.push(cosT, sinT, -thick * 0.5);
      normals.push(0, 0, -1);
    }

    for (let i = 0; i < segs; i += 1) {
      const f0 = 2 + i * 2;
      const f1 = 2 + (i + 1) * 2;
      indices.push(0, f0, f1);
      indices.push(1, f1 + 1, f0 + 1);
    }

    const rimBase = positions.length / 3;
    for (let i = 0; i <= segs; i += 1) {
      const th = startA + (i / segs) * (endA - startA);
      const cosT = Math.cos(th);
      const sinT = Math.sin(th);
      positions.push(cosT * r, sinT * r, thick * 0.5);
      positions.push(cosT * r, sinT * r, -thick * 0.5);
      normals.push(cosT, sinT, 0);
      normals.push(cosT, sinT, 0);
    }
    for (let i = 0; i < segs; i += 1) {
      const i0 = rimBase + i * 2;
      indices.push(i0, i0 + 1, i0 + 2, i0 + 2, i0 + 1, i0 + 3);
    }

    return { positions, normals, indices };
  }

  function makePoppetValve() {
    const positions = [];
    const normals = [];
    const indices = [];
    const segs = 18;
    const headR = 0.22;
    const stemR = 0.038;
    const stemH = 0.72;

    const centerB = positions.length / 3;
    positions.push(0, -0.04, 0);
    normals.push(0, -1, 0);
    for (let i = 0; i <= segs; i += 1) {
      const th = (i / segs) * Math.PI * 2;
      positions.push(Math.cos(th) * headR, 0, Math.sin(th) * headR);
      normals.push(Math.cos(th) * 0.7, -0.7, Math.sin(th) * 0.7);
    }
    for (let i = 0; i < segs; i += 1) {
      indices.push(centerB, centerB + 1 + i, centerB + 2 + i);
    }

    const stemBase = positions.length / 3;
    for (let i = 0; i <= segs; i += 1) {
      const th = (i / segs) * Math.PI * 2;
      const cosT = Math.cos(th);
      const sinT = Math.sin(th);
      positions.push(cosT * stemR, stemH, sinT * stemR);
      positions.push(cosT * stemR, 0, sinT * stemR);
      normals.push(cosT, 0, sinT);
      normals.push(cosT, 0, sinT);
    }
    for (let i = 0; i < segs; i += 1) {
      const i0 = stemBase + i * 2;
      indices.push(i0, i0 + 2, i0 + 1, i0 + 1, i0 + 2, i0 + 3);
    }

    return { positions, normals, indices };
  }

  function makeCamLobe() {
    const positions = [];
    const normals = [];
    const indices = [];
    const segs = 20;
    const baseR = 0.12;
    const lift = 0.10;
    const width = 0.14;
    const halfW = width * 0.5;

    function getLobeRadius(angle) {
      const cosA = Math.cos(angle);
      return baseR + (cosA > 0 ? cosA * cosA * lift : 0);
    }

    positions.push(0, 0, halfW);
    normals.push(0, 0, 1);
    positions.push(0, 0, -halfW);
    normals.push(0, 0, -1);

    for (let i = 0; i <= segs; i += 1) {
      const th = (i / segs) * Math.PI * 2;
      const r = getLobeRadius(th);
      positions.push(Math.cos(th) * r, Math.sin(th) * r, halfW);
      normals.push(0, 0, 1);
      positions.push(Math.cos(th) * r, Math.sin(th) * r, -halfW);
      normals.push(0, 0, -1);
    }

    for (let i = 0; i < segs; i += 1) {
      const f0 = 2 + i * 2;
      const f1 = 2 + (i + 1) * 2;
      indices.push(0, f0, f1);
      indices.push(1, f1 + 1, f0 + 1);
    }

    const rimBase = positions.length / 3;
    for (let i = 0; i <= segs; i += 1) {
      const th = (i / segs) * Math.PI * 2;
      const r = getLobeRadius(th);
      const cosT = Math.cos(th), sinT = Math.sin(th);
      positions.push(cosT * r, sinT * r, halfW);
      positions.push(cosT * r, sinT * r, -halfW);
      normals.push(cosT, sinT, 0);
      normals.push(cosT, sinT, 0);
    }
    for (let i = 0; i < segs; i += 1) {
      const i0 = rimBase + i * 2;
      indices.push(i0, i0 + 1, i0 + 2, i0 + 2, i0 + 1, i0 + 3);
    }

    return { positions, normals, indices };
  }

  function makeGear(teeth = 16, radius = 0.55, thickness = 0.12, holeRadius = 0.14) {
    const positions = [];
    const normals = [];
    const indices = [];
    const halfT = thickness * 0.5;
    const toothH = radius * 0.14;
    const rRoot = radius - toothH;
    const rTip = radius + toothH * 0.5;
    const numPts = teeth * 4;

    function getGearRadius(i) {
      const mod = i % 4;
      return (mod === 1 || mod === 2) ? rTip : rRoot;
    }

    // Front face (+Z)
    const frontCenter = positions.length / 3;
    positions.push(0, 0, halfT);
    normals.push(0, 0, 1);
    for (let i = 0; i <= numPts; i += 1) {
      const angle = (i / numPts) * Math.PI * 2;
      const r = getGearRadius(i);
      positions.push(Math.cos(angle) * r, Math.sin(angle) * r, halfT);
      normals.push(0, 0, 1);
    }
    for (let i = 0; i < numPts; i += 1) {
      indices.push(frontCenter, frontCenter + 1 + i, frontCenter + 2 + i);
    }

    // Back face (-Z)
    const backCenter = positions.length / 3;
    positions.push(0, 0, -halfT);
    normals.push(0, 0, -1);
    for (let i = 0; i <= numPts; i += 1) {
      const angle = (i / numPts) * Math.PI * 2;
      const r = getGearRadius(i);
      positions.push(Math.cos(angle) * r, Math.sin(angle) * r, -halfT);
      normals.push(0, 0, -1);
    }
    for (let i = 0; i < numPts; i += 1) {
      indices.push(backCenter, backCenter + 2 + i, backCenter + 1 + i);
    }

    // Outer perimeter teeth sides
    const rimBase = positions.length / 3;
    for (let i = 0; i <= numPts; i += 1) {
      const angle = (i / numPts) * Math.PI * 2;
      const r = getGearRadius(i);
      const cosA = Math.cos(angle), sinA = Math.sin(angle);
      positions.push(cosA * r, sinA * r, halfT);
      positions.push(cosA * r, sinA * r, -halfT);
      normals.push(cosA, sinA, 0);
      normals.push(cosA, sinA, 0);
    }
    for (let i = 0; i < numPts; i += 1) {
      const i0 = rimBase + i * 2;
      const i1 = i0 + 1;
      const i2 = i0 + 2;
      const i3 = i0 + 3;
      indices.push(i0, i2, i1, i1, i2, i3);
    }

    return { positions, normals, indices };
  }

  function makeFlywheel() {
    return makeGear(28, 0.92, 0.16, 0.22);
  }

  function makeTurboImpeller(blades = 8) {
    const hub = makeCylinder(16, 0.08, 0.28, 0.22);
    const positions = [...hub.positions];
    const normals = [...hub.normals];
    const indices = [...hub.indices];

    for (let b = 0; b < blades; b += 1) {
      const angle = (b / blades) * Math.PI * 2;
      const cosA = Math.cos(angle);
      const sinA = Math.sin(angle);
      const base = positions.length / 3;

      const rInner = 0.12, rOuter = 0.38;
      const h0 = 0.08, h1 = -0.08;

      positions.push(cosA * rInner, h0, sinA * rInner);
      positions.push(cosA * rOuter, h1, sinA * rOuter);
      positions.push(Math.cos(angle + 0.15) * rOuter, h1, Math.sin(angle + 0.15) * rOuter);
      positions.push(Math.cos(angle + 0.1) * rInner, h0, Math.sin(angle + 0.1) * rInner);

      const n = [-sinA, 0.4, cosA];
      for (let k = 0; k < 4; k++) normals.push(...n);
      indices.push(base, base + 3, base + 2, base, base + 2, base + 1);
    }
    return { positions, normals, indices };
  }

  // --- WebGL Shaders ---
  function createShader(gl, type, source) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      const info = gl.getShaderInfoLog(shader);
      gl.deleteShader(shader);
      throw new Error(info);
    }
    return shader;
  }

  function createProgram(gl) {
    const vertexSource = `
      precision highp float;
      attribute vec3 aPosition;
      attribute vec3 aNormal;
      uniform mat4 uModel;
      uniform mat4 uView;
      uniform mat4 uProjection;
      varying vec3 vNormal;
      varying vec3 vWorld;
      varying vec3 vViewPos;
      void main(){
        vec4 world = uModel * vec4(aPosition, 1.0);
        vWorld = world.xyz;
        vNormal = normalize(mat3(uModel) * aNormal);
        vec4 viewPos = uView * world;
        vViewPos = viewPos.xyz;
        gl_Position = uProjection * viewPos;
      }
    `;

    const fragmentSource = `
      precision highp float;
      uniform vec3 uColor;
      uniform float uAlpha;
      uniform float uGlow;
      uniform float uSelected;
      uniform float uMetallic;
      uniform float uRoughness;
      varying vec3 vNormal;
      varying vec3 vWorld;
      varying vec3 vViewPos;
      void main(){
        vec3 N = normalize(vNormal);
        vec3 V = normalize(-vViewPos);

        // 3-Point Studio Lighting Rig
        vec3 L1 = normalize(vec3(0.58, 0.82, 0.65));  // Key Light
        vec3 L2 = normalize(vec3(-0.65, 0.35, -0.5)); // Cool Fill Light
        vec3 L3 = normalize(vec3(0.0, -0.85, 0.52));  // Ground Bounce

        float diff1 = max(dot(N, L1), 0.0);
        float diff2 = max(dot(N, L2), 0.0) * 0.38;
        float diff3 = max(dot(N, L3), 0.0) * 0.18;
        float diffuse = diff1 + diff2 + diff3;

        // Blinn-Phong Specular for Machined Engineering Metals
        vec3 H1 = normalize(L1 + V);
        float specPower = mix(16.0, 96.0, uMetallic);
        float specFactor = mix(0.20, 0.85, uMetallic);
        float spec = pow(max(dot(N, H1), 0.0), specPower) * specFactor;

        // Fresnel Rim
        float rim = pow(1.0 - max(dot(N, V), 0.0), 3.0);

        vec3 ambient = uColor * mix(0.26, 0.14, uMetallic);
        vec3 baseColor = ambient + uColor * (0.74 * diffuse) + vec3(0.92, 0.96, 0.94) * spec;

        // Glow & Selection
        baseColor += uColor * uGlow * 0.75;
        if (uSelected > 0.5) {
          baseColor += vec3(0.35, 0.88, 0.48) * (rim * 0.75 + 0.20);
        }

        float alpha = uAlpha < 0.95 ? mix(uAlpha * 0.45, 0.85, rim * 0.75) : uAlpha;
        gl_FragColor = vec4(baseColor, alpha);
      }
    `;

    const vertex = createShader(gl, gl.VERTEX_SHADER, vertexSource);
    const fragment = createShader(gl, gl.FRAGMENT_SHADER, fragmentSource);
    const program = gl.createProgram();
    gl.attachShader(program, vertex);
    gl.attachShader(program, fragment);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      throw new Error(gl.getProgramInfoLog(program));
    }
    return program;
  }

  function uploadMesh(gl, source) {
    const position = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, position);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(source.positions), gl.STATIC_DRAW);

    const normal = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, normal);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(source.normals), gl.STATIC_DRAW);

    const index = gl.createBuffer();
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, index);
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint16Array(source.indices), gl.STATIC_DRAW);

    return { position, normal, index, count: source.indices.length };
  }

  // =========================================================================
  // Master AeroEngineSimulator Class
  // =========================================================================
  class AeroEngineSimulator {
    constructor(canvas, labelsCanvas) {
      this.canvas = canvas;
      this.labelsCanvas = labelsCanvas;
      this.labelsCtx = labelsCanvas && labelsCanvas.getContext ? labelsCanvas.getContext('2d') : null;

      this.gl = canvas.getContext('webgl', {
        antialias: true,
        alpha: true,
        premultipliedAlpha: false,
        powerPreference: 'high-performance',
        preserveDrawingBuffer: false
      });
      if (!this.gl) throw new Error('WebGL is unavailable');

      this.program = createProgram(this.gl);
      this.locations = {
        position: this.gl.getAttribLocation(this.program, 'aPosition'),
        normal: this.gl.getAttribLocation(this.program, 'aNormal'),
        model: this.gl.getUniformLocation(this.program, 'uModel'),
        view: this.gl.getUniformLocation(this.program, 'uView'),
        projection: this.gl.getUniformLocation(this.program, 'uProjection'),
        color: this.gl.getUniformLocation(this.program, 'uColor'),
        alpha: this.gl.getUniformLocation(this.program, 'uAlpha'),
        glow: this.gl.getUniformLocation(this.program, 'uGlow'),
        selected: this.gl.getUniformLocation(this.program, 'uSelected'),
        metallic: this.gl.getUniformLocation(this.program, 'uMetallic'),
        roughness: this.gl.getUniformLocation(this.program, 'uRoughness')
      };

      // Upload High-Precision Geometries
      this.meshes = {
        cube: uploadMesh(this.gl, makeCube()),
        cylinder: uploadMesh(this.gl, makeCylinder(24)),
        cutawayCylinder: uploadMesh(this.gl, makeCutawayCylinder(24, Math.PI * 0.75, Math.PI * 2.25, 0.44, 0.54, 1.0)),
        sphere: uploadMesh(this.gl, makeSphere(14, 20)),
        torus: uploadMesh(this.gl, makeTorus(24, 14, 0.5, 0.12)),
        spring: uploadMesh(this.gl, makeHelicalSpring(4.5, 0.14, 0.03, 0.42)),
        piston: uploadMesh(this.gl, makePiston()),
        connectingRod: uploadMesh(this.gl, makeConnectingRod()),
        crankLobe: uploadMesh(this.gl, makeCrankshaftWeb()),
        valve: uploadMesh(this.gl, makePoppetValve()),
        camLobe: uploadMesh(this.gl, makeCamLobe()),
        flywheel: uploadMesh(this.gl, makeFlywheel()),
        camGear: uploadMesh(this.gl, makeGear(24, 0.46, 0.08, 0.12)),
        crankGear: uploadMesh(this.gl, makeGear(12, 0.28, 0.08, 0.10)),
        impeller: uploadMesh(this.gl, makeTurboImpeller(8))
      };

      this.telemetry = {
        rpm: 3000,
        throttle: 58,
        cht: 220,
        egt: 1200,
        oilPressure: 60,
        oilTemp: 85,
        fuelFlow: 20,
        vibration: 1.02,
        busVoltage: 28.2,
        health: 100,
        fault: 'none',
        engineState: 'TAKEOFF_CLIMB'
      };

      // Authoritative 4-Stroke Crank Angle (0 to 4*PI radians = 0 to 720 degrees)
      this.crankAngle = 0;
      this.turboAngle = 0;
      this.simRpm = 3000;
      this.playbackSpeed = 1.0;
      this.isPaused = false;
      this.isTelemetrySynced = true;

      // Mode and Overlays
      this.mode = 'normal';
      this.xray = false;
      this.exploded = false;
      this.explodeAmount = 0;
      this.showLabels = true;
      this.activeCylinder = 0;

      // Camera: 3/4 Isometric Perspective
      this.camera = { yaw: -38 * DEG, pitch: 22 * DEG, distance: 10.5, target: [0, 0.35, 0] };
      this.selected = 'pistons';
      this.drag = null;
      this.pickTargets = [];
      this.labelNodes = [];
      this.lastTime = performance.now();
      this.reducedMotion = typeof matchMedia === 'function' ? matchMedia('(prefers-reduced-motion: reduce)').matches : false;

      // Dynamic 2D Diagram Canvases
      this.kinematicsCanvas = document.getElementById('diagramKinematicsCanvas');
      this.valveCanvas = document.getElementById('diagramValveCanvas');
      this.pressureCanvas = document.getElementById('diagramPressureCanvas');

      this.configureGl();
      this.bindInteractions();
      this.bindControls();

      if (typeof ResizeObserver !== 'undefined') {
        this.resizeObserver = new ResizeObserver(() => this.resize());
        if (canvas.parentElement) {
          this.resizeObserver.observe(canvas.parentElement);
        }
      }
      this.resize();
      this.updateInspector();
      this.updateThermalField();
      requestAnimationFrame(time => this.frame(time));
    }

    configureGl() {
      const gl = this.gl;
      gl.useProgram(this.program);
      gl.enable(gl.DEPTH_TEST);
      gl.depthFunc(gl.LEQUAL);
      gl.enable(gl.CULL_FACE);
      gl.cullFace(gl.BACK);
      gl.enable(gl.BLEND);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
      gl.clearColor(0.0, 0.0, 0.0, 0.0);
    }

    resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2.5);
      const rect = this.canvas.getBoundingClientRect();
      const width = Math.max(320, Math.round(rect.width * dpr));
      const height = Math.max(260, Math.round(rect.height * dpr));
      if (this.canvas.width !== width || this.canvas.height !== height) {
        this.canvas.width = width;
        this.canvas.height = height;
        this.gl.viewport(0, 0, width, height);
      }
      if (this.labelsCanvas && (this.labelsCanvas.width !== width || this.labelsCanvas.height !== height)) {
        this.labelsCanvas.width = width;
        this.labelsCanvas.height = height;
      }
    }

    resetCamera() {
      this.camera = { yaw: -38 * DEG, pitch: 22 * DEG, distance: 10.5, target: [0, 0.35, 0] };
    }

    setCameraPreset(preset) {
      if (preset === 'hero') {
        this.camera = { yaw: -38 * DEG, pitch: 22 * DEG, distance: 10.5, target: [0, 0.35, 0] };
      } else if (preset === 'front') {
        this.camera = { yaw: 0, pitch: 0, distance: 9.5, target: [0, 0.45, 0] };
      } else if (preset === 'top') {
        this.camera = { yaw: 0, pitch: 88 * DEG, distance: 9.0, target: [0, 0.5, 0] };
      } else if (preset === 'side') {
        this.camera = { yaw: -90 * DEG, pitch: 0, distance: 9.5, target: [0, 0.45, 0] };
      } else if (preset === 'cylinder') {
        const cylXs = [-1.80, -0.60, 0.60, 1.80];
        const cx = cylXs[this.activeCylinder];
        this.camera = { yaw: -25 * DEG, pitch: 18 * DEG, distance: 5.2, target: [cx, 0.95, 0] };
      }
    }

    setMode(mode) {
      this.mode = ['normal', 'thermal', 'vibration'].includes(mode) ? mode : 'normal';
      document.querySelectorAll('[data-engine-mode]').forEach(button => {
        button.classList.toggle('active', button.dataset.engineMode === this.mode);
      });
      const modeLabel = document.getElementById('engineModeLabel');
      if (modeLabel) modeLabel.textContent = this.mode.toUpperCase();
      this.updateThermalField();
    }

    setTelemetry(data) {
      const numeric = ['rpm', 'throttle', 'cht', 'egt', 'oilPressure', 'oilTemp', 'fuelFlow', 'vibration', 'busVoltage', 'health'];
      numeric.forEach(key => {
        const value = Number(data[key]);
        if (Number.isFinite(value)) this.telemetry[key] = value;
      });
      if (data.fault != null) this.telemetry.fault = String(data.fault);
      if (data.engineState != null) this.telemetry.engineState = String(data.engineState);
      if (data.engine_run_state != null) this.telemetry.engineState = String(data.engine_run_state);

      if (this.isTelemetrySynced) {
        this.simRpm = Math.max(0, this.telemetry.rpm);
        const rpmSlider = document.getElementById('simRpmSlider');
        if (rpmSlider) rpmSlider.value = this.simRpm;
        const rpmVal = document.getElementById('simRpmVal');
        if (rpmVal) rpmVal.textContent = `${Math.round(this.simRpm)} RPM`;
      }

      this.updateHud();
      this.updateInspector();
      this.updateThermalField();
    }

    updateThermalField() {
      const t = this.telemetry;
      const chtLevel = clamp((t.cht - 180) / (315 - 180), 0, 1);
      const egtLevel = clamp((t.egt - 850) / (1500 - 850), 0, 1);
      const level = Math.max(chtLevel, egtLevel * 0.94);
      const color = thermalColor(level, 0, 1).map(channel => Math.round(channel * 255));
      const viewport = this.canvas.closest ? this.canvas.closest('.engine-viewport') : null;
      if (viewport) {
        if (viewport.classList && viewport.classList.toggle) {
          viewport.classList.toggle('thermal-active', this.mode === 'thermal');
        }
        if (viewport.style && viewport.style.setProperty) {
          viewport.style.setProperty('--thermal-rgb', color.join(', '));
          viewport.style.setProperty('--thermal-level', level.toFixed(3));
        }
      }
      const value = document.getElementById('engineThermalValue');
      if (value) value.textContent = `${Math.round(t.cht)}°F CHT · ${Math.round(t.egt).toLocaleString()}°F EGT`;
      const marker = document.getElementById('engineThermalMarker');
      if (marker && marker.style) marker.style.left = `${Math.round(level * 100)}%`;
      const field = document.getElementById('engineThermalField');
      if (field) {
        const state = level >= 0.86 ? 'critical' : level >= 0.7 ? 'hot' : level >= 0.34 ? 'nominal' : 'cool';
        if (field.dataset) field.dataset.thermalState = state;
        else if (field.setAttribute) field.setAttribute('data-thermal-state', state);
      }
    }

    updateHud() {
      const degCrank = Math.round((this.crankAngle * RAD) % 720);
      const values = {
        engineHudRpm: `${Math.round(this.simRpm).toLocaleString()} RPM`,
        engineHudCht: `${Math.round(this.telemetry.cht)}°F CHT`,
        engineHudEgt: `${Math.round(this.telemetry.egt)}°F EGT`,
        engineHudOil: `${this.telemetry.oilPressure.toFixed(0)} PSI OIL`,
        engineHudVibration: `${this.telemetry.vibration.toFixed(2)} g RMS`,
        engineHudCrank: `${degCrank}° CRANK`
      };
      Object.entries(values).forEach(([id, value]) => {
        const element = document.getElementById(id);
        if (element) element.textContent = value;
      });
      const state = document.getElementById('engineTwinState');
      if (state) {
        const fault = this.telemetry.fault.toLowerCase();
        state.textContent = fault && fault !== 'none' ? `FAULT FOCUS • ${this.telemetry.fault.toUpperCase()}` : 'DIGITAL TWIN SYNCHRONIZED';
        state.className = fault && fault !== 'none' ? 'engine-twin-state warn' : 'engine-twin-state';
      }
    }

    componentData(component) {
      const t = this.telemetry;
      const fault = t.fault.toLowerCase();
      const deg = Math.round((this.crankAngle * RAD) % 720);
      const entries = {
        pistons: ['Piston & Connecting Rod Assembly', `${Math.round(this.simRpm)} RPM`, `${deg}° Slider-Crank`, 'Machined aluminum pistons, 3 compression & scraper rings, forged H-beam rods'],
        crankcase: ['Crankcase Bedplate & Block', `${Math.round(this.simRpm)} RPM`, `${t.vibration.toFixed(2)} g RMS`, 'Inline-4 structural crankcase with cross-bolted main bearing saddles'],
        cylinders: ['Crystal Cutaway Cylinders', `${Math.round(t.cht)}°F CHT`, `${Math.round(t.egt)}°F EGT`, 'Mirror-honed cylinder sleeves, water jacket channels, combustion chambers'],
        crankshaft: ['Forged Crankshaft & Counterweights', `${Math.round(this.simRpm)} RPM`, '180° Flat-Plane', 'Flat-plane forged steel crankshaft with 8 balance counterweights and toothed flywheel'],
        valvetrain: ['DOHC Valvetrain & Compressing Springs', `${Math.round(this.simRpm * 0.5)} RPM Cam`, '1:2 Speed Ratio', 'Dual overhead camshafts, 8 poppet valves, and dynamic compressing helical coil springs'],
        turbo: ['Turbocharger & Boost Turbine', `${Math.max(0.6, 0.55 + t.throttle / 100).toFixed(2)} bar Boost`, `${Math.round(t.egt)}°F Turbine`, 'High-speed compressor wheel, exhaust turbine volute, wastegate actuator'],
        fuel: ['Common-Rail Direct Fuel Injection', `${t.fuelFlow.toFixed(1)} L/h`, 'High-Pressure Rail', 'High-pressure common-rail manifold with 4 solenoid direct injectors'],
        lubrication: ['Lubrication System & Oil Sump', `${t.oilPressure.toFixed(1)} PSI`, `${t.oilTemp.toFixed(1)}°C`, 'Ribbed cast aluminum sump pan, spin-on filter, pressurized galleries with dynamic flow'],
        propeller: ['Reduction Drive & Flywheel', `${Math.round(this.simRpm * 0.46)} RPM Prop`, 'Spur Flywheel', 'Precision toothed spur flywheel and propeller reduction drive flange'],
        electrical: ['Alternator & FADEC Dual ECU', `${t.busVoltage.toFixed(1)} V Bus`, `${Math.round(t.health)}% Health`, '28V brushless alternator and dual-channel FADEC engine control computer'],
        sensors: ['Virtual Sensor Suite', `${Math.round(t.health)}% Trust`, fault.includes('sensor') ? 'DRIFT DETECTED' : 'NOMINAL', 'Redundant sensor probes (CHT, EGT, MAP, Oil P/T, Crank Position)']
      };
      return entries[component] || entries.pistons;
    }

    updateInspector() {
      const data = this.componentData(this.selected);
      const fault = this.telemetry.fault;
      const ids = {
        selectedComponentName: data[0],
        selectedComponentPrimary: data[1],
        selectedComponentSecondary: data[2],
        selectedComponentDetail: data[3],
        selectedComponentFault: fault && fault.toLowerCase() !== 'none' ? fault : 'No active fault evidence'
      };
      Object.entries(ids).forEach(([id, value]) => {
        const element = document.getElementById(id);
        if (element) element.textContent = value;
      });
    }

    bindControls() {
      const on = (id, event, handler) => {
        const element = document.getElementById(id);
        if (element) element.addEventListener(event, handler);
      };

      on('engineResetCamera', 'click', () => this.resetCamera());

      on('enginePause', 'click', event => {
        this.isPaused = !this.isPaused;
        event.currentTarget.classList.toggle('active', this.isPaused);
        event.currentTarget.textContent = this.isPaused ? '▶ Play' : '⏸ Pause';
        const playBtn = document.getElementById('simPlayBtn');
        if (playBtn) playBtn.textContent = this.isPaused ? '▶' : '⏸';
      });

      on('simPlayBtn', 'click', () => {
        this.isPaused = !this.isPaused;
        const mainPause = document.getElementById('enginePause');
        if (mainPause) {
          mainPause.classList.toggle('active', this.isPaused);
          mainPause.textContent = this.isPaused ? '▶ Play' : '⏸ Pause';
        }
        const playBtn = document.getElementById('simPlayBtn');
        if (playBtn) playBtn.textContent = this.isPaused ? '▶' : '⏸';
      });

      on('simStepBack', 'click', () => {
        this.isPaused = true;
        this.crankAngle = (this.crankAngle - 15 * DEG + Math.PI * 4) % (Math.PI * 4);
        this.syncScrubber();
      });

      on('simStepForward', 'click', () => {
        this.isPaused = true;
        this.crankAngle = (this.crankAngle + 15 * DEG) % (Math.PI * 4);
        this.syncScrubber();
      });

      on('simScrubber', 'input', event => {
        this.isPaused = true;
        const deg = parseFloat(event.target.value);
        this.crankAngle = (deg * DEG) % (Math.PI * 4);
        const mainPause = document.getElementById('enginePause');
        if (mainPause) {
          mainPause.classList.add('active');
          mainPause.textContent = '▶ Play';
        }
        const playBtn = document.getElementById('simPlayBtn');
        if (playBtn) playBtn.textContent = '▶';
        this.syncScrubber();
      });

      on('simSpeedSelect', 'change', event => {
        this.playbackSpeed = parseFloat(event.target.value) || 1.0;
      });

      on('simRpmSlider', 'input', event => {
        this.simRpm = parseFloat(event.target.value);
        this.isTelemetrySynced = false;
        const rpmVal = document.getElementById('simRpmVal');
        if (rpmVal) rpmVal.textContent = `${Math.round(this.simRpm)} RPM`;
        const syncBtn = document.getElementById('simSyncRpmBtn');
        if (syncBtn) syncBtn.classList.remove('active');
      });

      on('simSyncRpmBtn', 'click', event => {
        this.isTelemetrySynced = true;
        event.currentTarget.classList.add('active');
        this.simRpm = Math.max(0, this.telemetry.rpm);
        const rpmSlider = document.getElementById('simRpmSlider');
        if (rpmSlider) rpmSlider.value = this.simRpm;
        const rpmVal = document.getElementById('simRpmVal');
        if (rpmVal) rpmVal.textContent = `${Math.round(this.simRpm)} RPM`;
      });

      on('engineXray', 'click', event => {
        this.xray = !this.xray;
        event.currentTarget.classList.toggle('active', this.xray);
      });

      on('engineExplode', 'click', event => {
        this.exploded = !this.exploded;
        event.currentTarget.classList.toggle('active', this.exploded);
      });

      on('engineLabels', 'click', event => {
        this.showLabels = !this.showLabels;
        event.currentTarget.classList.toggle('active', this.showLabels);
      });

      if (document.querySelectorAll) {
        document.querySelectorAll('[data-camera-preset]').forEach(btn => {
          btn.addEventListener('click', () => {
            document.querySelectorAll('[data-camera-preset]').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            this.setCameraPreset(btn.dataset.cameraPreset);
          });
        });

        document.querySelectorAll('[data-cylinder-focus]').forEach(btn => {
          btn.addEventListener('click', () => {
            document.querySelectorAll('[data-cylinder-focus]').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            this.activeCylinder = parseInt(btn.dataset.cylinderFocus, 10) || 0;
          });
        });

        document.querySelectorAll('[data-engine-mode]').forEach(button => {
          button.addEventListener('click', () => this.setMode(button.dataset.engineMode));
        });
      }
    }

    syncScrubber() {
      const deg = Math.round((this.crankAngle * RAD) % 720);
      const scrubber = document.getElementById('simScrubber');
      if (scrubber && document.activeElement !== scrubber) scrubber.value = deg;
      const degReadout = document.getElementById('simAngleReadout');
      if (degReadout) degReadout.textContent = `${deg}°`;

      const cylOffsets = [0, Math.PI * 3, Math.PI * 1, Math.PI * 2];
      const cylAngle = (this.crankAngle + cylOffsets[this.activeCylinder]) % (Math.PI * 4);
      let phaseName = 'INTAKE';
      let phaseClass = 'phase-intake';
      if (cylAngle < Math.PI) {
        phaseName = 'INTAKE';
        phaseClass = 'phase-intake';
      } else if (cylAngle < Math.PI * 2) {
        phaseName = 'COMPRESSION';
        phaseClass = 'phase-compression';
      } else if (cylAngle < Math.PI * 3) {
        phaseName = 'POWER';
        phaseClass = 'phase-power';
      } else {
        phaseName = 'EXHAUST';
        phaseClass = 'phase-exhaust';
      }

      const phaseBadge = document.getElementById('simPhaseBadge');
      if (phaseBadge) {
        phaseBadge.textContent = phaseName;
        phaseBadge.className = `sim-phase-badge ${phaseClass}`;
      }

      // Update Firing Order Ribbon
      for (let i = 0; i < 4; i++) {
        const ca = (this.crankAngle + cylOffsets[i]) % (Math.PI * 4);
        const card = document.getElementById(`firingCyl${i + 1}`);
        if (card) {
          const isPower = ca >= Math.PI * 2 && ca < Math.PI * 3;
          if (card.classList && card.classList.toggle) card.classList.toggle('active-power', isPower);
          const pLabel = card.querySelector ? card.querySelector('.cyl-phase-label') : null;
          if (pLabel) {
            if (ca < Math.PI) pLabel.textContent = 'INTAKE';
            else if (ca < Math.PI * 2) pLabel.textContent = 'COMPR';
            else if (ca < Math.PI * 3) pLabel.textContent = 'POWER';
            else pLabel.textContent = 'EXHAUST';
          }
        }
      }
    }

    bindInteractions() {
      this.canvas.addEventListener('pointerdown', event => {
        if (this.canvas.setPointerCapture) this.canvas.setPointerCapture(event.pointerId);
        this.drag = {
          button: event.button,
          x: event.clientX,
          y: event.clientY,
          startX: event.clientX,
          startY: event.clientY
        };
      });

      this.canvas.addEventListener('pointermove', event => {
        if (!this.drag) return;
        const dx = event.clientX - this.drag.x;
        const dy = event.clientY - this.drag.y;

        if (this.drag.button === 2 || event.shiftKey) {
          const factor = 0.005 * (this.camera.distance / 10);
          this.camera.target[0] -= dx * factor * Math.cos(this.camera.yaw);
          this.camera.target[1] += dy * factor;
          this.camera.target[2] -= dx * factor * Math.sin(this.camera.yaw);
        } else {
          this.camera.yaw -= dx * 0.007;
          this.camera.pitch = clamp(this.camera.pitch - dy * 0.006, -1.15, 1.15);
        }
        this.drag.x = event.clientX;
        this.drag.y = event.clientY;
      });

      this.canvas.addEventListener('pointerup', event => {
        if (!this.drag) return;
        const moved = Math.hypot(event.clientX - this.drag.startX, event.clientY - this.drag.startY);
        if (moved < 6) this.pick(event);
        this.drag = null;
      });

      this.canvas.addEventListener('contextmenu', e => e.preventDefault());

      this.canvas.addEventListener('wheel', event => {
        event.preventDefault();
        this.camera.distance = clamp(this.camera.distance + event.deltaY * 0.010, 4.0, 20.0);
      }, { passive: false });

      this.canvas.addEventListener('dblclick', () => this.resetCamera());
    }

    pick(event) {
      const rect = this.canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      let winner = null;
      this.pickTargets.forEach(target => {
        const distance = Math.hypot(target.x - x, target.y - y);
        if (distance < target.radius && (!winner || distance < winner.distance)) {
          winner = { ...target, distance };
        }
      });
      if (winner) {
        this.selected = winner.component;
        this.updateInspector();
      }
    }

    part(mesh, component, label, position, rotation, scale, color, options = {}) {
      return {
        mesh,
        component,
        label,
        position,
        rotation,
        scale,
        color,
        alpha: options.alpha ?? 1.0,
        glow: options.glow ?? 0.0,
        metallic: options.metallic ?? 0.5,
        roughness: options.roughness ?? 0.5,
        pick: options.pick ?? false,
        leadLabel: options.leadLabel ?? null
      };
    }

    // =========================================================================
    // Mechanical Scene Assembly (Inline-4 4-Stroke Cutaway Digital Twin)
    // =========================================================================
    buildParts(time) {
      const t = this.telemetry;
      const fault = t.fault.toLowerCase();
      const thermal = this.mode === 'thermal';
      const explosion = this.explodeAmount;

      // Realistic Materials Palette
      const darkBlock = hexColor('#1c261e');
      const castAlum = hexColor('#566458');
      const polishedSteel = hexColor('#cdd6cf');
      const forgedSteel = hexColor('#8a988c');
      const machinedCrown = hexColor('#c2d1c5');
      const pistonSkirt = hexColor('#3a473c');
      const chromeRing = hexColor('#9bb0a0');
      const bronze = hexColor('#bfa054');
      const exhaustIron = hexColor('#5a3825');
      const intakeAlum = hexColor('#629472');
      const springSteel = hexColor('#a2aea4');
      const cyan = hexColor('#5eb574');
      const green = hexColor('#4cb574');
      const amber = hexColor('#c9983e');
      const red = hexColor('#c94c48');

      const oilColor = fault.includes('lubric') || t.oilPressure < 20 ? red : green;
      const fuelColor = fault.includes('inject') ? amber : cyan;
      const electricColor = fault.includes('elect') || fault.includes('battery') || t.busVoltage < 24 ? red : cyan;

      const cylinderThermal = thermal ? thermalColor(t.cht, 180, 315) : castAlum;
      const exhaustThermal = thermal ? thermalColor(t.egt, 850, 1500) : exhaustIron;
      const thermalIntensity = Math.max(
        clamp((t.cht - 180) / (315 - 180), 0, 1),
        clamp((t.egt - 850) / (1500 - 850), 0, 1) * 0.94
      );

      const housingAlpha = this.xray ? 0.22 : 1.0;
      const parts = [];
      const add = (...args) => parts.push(this.part(...args));

      // Inline-4 Geometry Parameters
      const cylXs = [-1.80, -0.60, 0.60, 1.80];
      const crankR = 0.48;
      const rodL = 1.35;

      // 4-Stroke Phase Angles (720-deg cycle): Firing order 1 - 3 - 4 - 2
      const cycleAngles = [
        (this.crankAngle + 0) % (Math.PI * 4),
        (this.crankAngle + Math.PI * 3) % (Math.PI * 4),
        (this.crankAngle + Math.PI * 1) % (Math.PI * 4),
        (this.crankAngle + Math.PI * 2) % (Math.PI * 4)
      ];

      // 1. Crankcase Bedplate & Block
      add('cube', 'crankcase', 'Crankcase Bedplate', [0, -0.45 - explosion * 0.35, 0], [0, 0, 0], [4.9, 0.45, 1.6], darkBlock, { alpha: housingAlpha, metallic: 0.4, pick: true, leadLabel: 'Crankcase Bedplate' });
      add('cube', 'crankcase', 'Block Rear Wall', [0, 0.85, -0.65], [0, 0, 0], [4.9, 1.8, 0.35], darkBlock, { alpha: housingAlpha, metallic: 0.3 });
      add('cube', 'crankcase', 'Block End Wall Front', [-2.45, 0.85, 0], [0, 0, 0], [0.35, 1.8, 1.5], darkBlock, { alpha: housingAlpha });
      add('cube', 'crankcase', 'Block End Wall Rear', [2.45, 0.85, 0], [0, 0, 0], [0.35, 1.8, 1.5], darkBlock, { alpha: housingAlpha });

      // Cylinder 4 Outer Wall
      add('cylinder', 'cylinders', 'Cylinder 4 Outer Barrel', [1.80, 0.95, 0], [0, 0, 0], [1.08, 1.08, 1.65], cylinderThermal, { alpha: housingAlpha, metallic: 0.4, pick: true });
      add('torus', 'cylinders', 'Cooling Jacket Rib 1', [1.80, 0.70, 0], [Math.PI / 2, 0, 0], [1.14, 1.14, 0.16], darkBlock, { alpha: housingAlpha });
      add('torus', 'cylinders', 'Cooling Jacket Rib 2', [1.80, 1.20, 0], [Math.PI / 2, 0, 0], [1.14, 1.14, 0.16], darkBlock, { alpha: housingAlpha });

      // Cylinders 1, 2, 3 Crystal Cutaway Sleeves
      for (let i = 0; i < 3; i++) {
        add('cutawayCylinder', 'cylinders', `Cylinder Liner ${i + 1}`, [cylXs[i], 0.95, 0], [0, 0, 0], [1.0, 1.65, 1.0], hexColor('#8e9c90'), {
          metallic: 0.85,
          roughness: 0.15,
          pick: true,
          leadLabel: i === 0 ? 'Crystal Cylinder Liner' : null
        });
      }

      // 2. Crankshaft & Main Bearings
      const mainXs = [-2.40, -1.20, 0.0, 1.20, 2.40];
      mainXs.forEach((mx, idx) => {
        add('cylinder', 'crankshaft', `Main Journal ${idx + 1}`, [mx, 0, 0], [0, 0, Math.PI / 2], [0.36, 0.36, 0.32], polishedSteel, { metallic: 0.9, roughness: 0.15, pick: true });
        add('cube', 'crankcase', `Bearing Saddle ${idx + 1}`, [mx, -0.16, 0], [0, 0, 0], [0.26, 0.30, 0.65], darkBlock, { alpha: housingAlpha });
      });

      // Crankpins, Webs & Toothed Flywheel
      cylXs.forEach((cx, idx) => {
        const phi = cycleAngles[idx] % (Math.PI * 2);
        const pinY = Math.cos(phi) * crankR;
        const pinZ = Math.sin(phi) * crankR;

        add('cylinder', 'crankshaft', `Crankpin ${idx + 1}`, [cx, pinY, pinZ], [0, 0, Math.PI / 2], [0.32, 0.32, 0.38], polishedSteel, { metallic: 0.95, roughness: 0.1, pick: true });

        [-0.22, 0.22].forEach(wOffset => {
          add('crankLobe', 'crankshaft', `Counterweight ${idx + 1}`, [cx + wOffset, 0, 0], [phi + Math.PI, 0, Math.PI / 2], [1.0, 1.0, 1.0], forgedSteel, {
            metallic: 0.7,
            roughness: 0.35,
            leadLabel: idx === 0 && wOffset === -0.22 ? 'Crank Counterweight' : null
          });
        });
      });

      // Toothed Spur Flywheel & Crank Gear
      const flyX = 2.48 + explosion * 0.4;
      add('flywheel', 'crankshaft', 'Toothed Spur Flywheel', [flyX, 0, 0], [0, 0, Math.PI / 2 + this.crankAngle], [1, 1, 1], forgedSteel, { metallic: 0.85, roughness: 0.2, pick: true, leadLabel: 'Spur Flywheel' });
      add('crankGear', 'valvetrain', 'Crank Timing Gear', [-2.45 - explosion * 0.3, 0, 0], [0, 0, Math.PI / 2 + this.crankAngle], [1, 1, 1], forgedSteel, { metallic: 0.85 });

      // 3. Pistons, Rods, Rings & Thermal Field
      cylXs.forEach((cx, idx) => {
        const cycle = cycleAngles[idx];
        const phi = cycle % (Math.PI * 2);

        // Exact slider-crank displacement
        const pinY = Math.cos(phi) * crankR;
        const pinZ = Math.sin(phi) * crankR;
        const pistonY = pinY + Math.sqrt(rodL * rodL - (pinZ * pinZ));
        const rodAngle = Math.asin(pinZ / rodL);

        const misfire = fault.includes('misfire') && idx === 1;
        const hotCyl = (fault.includes('overheat') || fault.includes('thermal')) && (idx === 1 || idx === 2);

        const isCombustionStroke = cycle >= 0 && cycle < Math.PI;
        const powerProgress = isCombustionStroke ? Math.sin((cycle / Math.PI) * Math.PI) : 0;
        const strokeHeatBoost = isCombustionStroke && this.simRpm > 200 ? powerProgress * 45 : 0;
        const cylCht = t.cht + (hotCyl ? 48 : (idx === 1 ? 8 : -4));
        const pistonCrownTemp = cylCht + 0.28 * Math.max(0, t.egt - cylCht) * (t.throttle / 100) + strokeHeatBoost;
        const crownHeatColor = thermalColor(pistonCrownTemp, 180, 315);
        const ring1Color = thermalColor(pistonCrownTemp * 0.88, 180, 315);
        const ring2Color = thermalColor(pistonCrownTemp * 0.76, 180, 315);
        const ring3Color = thermalColor(pistonCrownTemp * 0.64, 180, 315);

        const pColor = hotCyl ? red : thermal ? ring2Color : pistonSkirt;

        // Piston assembly
        add('piston', 'pistons', `Piston ${idx + 1}`, [cx, pistonY + 0.15 + explosion * 0.6, 0], [0, 0, 0], [1.0, 1.0, 1.0], pColor, {
          metallic: 0.85,
          roughness: 0.25,
          glow: misfire ? 0.6 : hotCyl ? 0.8 : (thermal ? 0.25 : 0),
          pick: true,
          leadLabel: idx === 0 ? 'Machined Piston' : null
        });

        // Polished Crown Disk
        add('cylinder', 'pistons', `Piston Crown ${idx + 1}`, [cx, pistonY + 0.40 + explosion * 0.6, 0], [0, 0, 0], [0.82, 0.82, 0.04], thermal ? crownHeatColor : machinedCrown, {
          metallic: 0.95,
          roughness: 0.1,
          glow: thermal ? 0.65 + powerProgress * 0.4 : 0,
          pick: true
        });

        // 3 Compression & Scraper Rings
        add('torus', 'pistons', `Compression Ring 1 - Cyl ${idx + 1}`, [cx, pistonY + 0.34 + explosion * 0.6, 0], [Math.PI / 2, 0, 0], [0.83, 0.83, 0.035], thermal ? ring1Color : chromeRing, {
          metallic: 0.95,
          glow: thermal ? 0.45 : 0
        });
        add('torus', 'pistons', `Scraper Ring 2 - Cyl ${idx + 1}`, [cx, pistonY + 0.26 + explosion * 0.6, 0], [Math.PI / 2, 0, 0], [0.83, 0.83, 0.035], thermal ? ring2Color : chromeRing, {
          metallic: 0.95,
          glow: thermal ? 0.30 : 0
        });
        add('torus', 'pistons', `Oil Ring 3 - Cyl ${idx + 1}`, [cx, pistonY + 0.18 + explosion * 0.6, 0], [Math.PI / 2, 0, 0], [0.83, 0.83, 0.035], thermal ? ring3Color : chromeRing, {
          metallic: 0.95,
          glow: thermal ? 0.18 : 0
        });

        // Wrist Pin
        add('cylinder', 'pistons', `Wrist Pin ${idx + 1}`, [cx, pistonY + explosion * 0.6, 0], [0, 0, Math.PI / 2], [0.14, 0.14, 0.52], polishedSteel, {
          metallic: 0.95,
          roughness: 0.1
        });

        // Forged H-Beam Connecting Rod
        const rodMidY = (pinY + pistonY) * 0.5 + explosion * 0.3;
        const rodMidZ = pinZ * 0.5;
        const rodColor = thermal ? thermalColor(pistonCrownTemp * 0.55, 180, 315) : forgedSteel;
        add('connectingRod', 'pistons', `Connecting Rod ${idx + 1}`, [cx, rodMidY, rodMidZ], [-rodAngle, 0, 0], [1.0, 1.0, 1.0], rodColor, {
          metallic: 0.75,
          roughness: 0.3,
          leadLabel: idx === 0 ? 'Forged H-Beam Rod' : null
        });

        // Thermal Dome & Heat Flux
        if (thermal || hotCyl || (t.cht > 230 && isCombustionStroke)) {
          const domeAlpha = 0.14 + thermalIntensity * 0.24 + powerProgress * 0.25;
          const domeGlow = 0.75 + thermalIntensity * 0.35 + powerProgress * 0.45;
          add('sphere', 'pistons', `Thermal Projection Dome ${idx + 1}`, [cx, pistonY + 0.54, 0], [0, 0, 0], [0.86, 0.42, 0.86], crownHeatColor, {
            alpha: clamp(domeAlpha, 0.08, 0.65),
            glow: clamp(domeGlow, 0.5, 1.2)
          });
          add('torus', 'pistons', `Thermal Heat Flux Boundary ${idx + 1}`, [cx, pistonY + 0.41, 0], [Math.PI / 2, 0, 0], [0.94, 0.94, 0.05], crownHeatColor, {
            alpha: 0.28 + thermalIntensity * 0.35,
            glow: 0.85 + powerProgress * 0.35
          });
        }

        // Combustion Flash
        if (isCombustionStroke && this.simRpm > 200) {
          const flashColor = misfire ? hexColor('#4a3c20') : hexColor('#ff9922');
          add('sphere', 'cylinders', `Combustion Flash ${idx + 1}`, [cx, 1.82, 0], [0, 0, 0], [0.72 * powerProgress, 0.32 * powerProgress, 0.72 * powerProgress], flashColor, {
            alpha: 0.30 + powerProgress * 0.60,
            glow: 0.95 + powerProgress * 0.55
          });
        }
      });

      // 4. Cylinder Head Deck & DOHC Valvetrain
      const headY = 1.95 + explosion * 1.5;
      add('cube', 'cylinders', 'Cylinder Head Deck Rear', [0, headY, -0.38], [0, 0, 0], [4.9, 0.48, 0.75], cylinderThermal, { alpha: housingAlpha, metallic: 0.45, pick: true, leadLabel: 'Cylinder Head' });
      add('cube', 'cylinders', 'Cylinder Head Deck Cyl 4', [1.80, headY, 0.38], [0, 0, 0], [1.2, 0.48, 0.75], cylinderThermal, { alpha: housingAlpha, metallic: 0.45, pick: true });

      // Dual Camshafts (Exact 1:2 Speed Ratio)
      const camY = headY + 0.65;
      const camAngle = this.crankAngle * 0.5;

      add('cylinder', 'valvetrain', 'Intake Camshaft', [0, camY, 0.32], [0, 0, Math.PI / 2], [0.12, 0.12, 4.8], forgedSteel, { metallic: 0.85, pick: true, leadLabel: 'Intake Camshaft (1/2 Speed)' });
      add('cylinder', 'valvetrain', 'Exhaust Camshaft', [0, camY, -0.32], [0, 0, Math.PI / 2], [0.12, 0.12, 4.8], forgedSteel, { metallic: 0.85, pick: true });

      // Timing Drive Gears
      add('camGear', 'valvetrain', 'Intake Cam Timing Gear', [-2.45 - explosion * 0.3, camY, 0.32], [0, 0, Math.PI / 2 + camAngle], [1, 1, 1], forgedSteel, { metallic: 0.85 });
      add('camGear', 'valvetrain', 'Exhaust Cam Timing Gear', [-2.45 - explosion * 0.3, camY, -0.32], [0, 0, Math.PI / 2 + camAngle], [1, 1, 1], forgedSteel, { metallic: 0.85 });

      // 8 Poppet Valves & Dynamic Compressing Helical Springs
      cylXs.forEach((cx, idx) => {
        const cycle = cycleAngles[idx];

        // Intake valve: opens 0 to PI (0-180 deg)
        let intakeLift = 0;
        if (cycle >= 0 && cycle < Math.PI) {
          intakeLift = Math.sin(cycle) * 0.15;
        }

        // Exhaust valve: opens 3*PI to 4*PI (540-720 deg)
        let exhaustLift = 0;
        if (cycle >= Math.PI * 3 && cycle < Math.PI * 4) {
          exhaustLift = Math.sin(cycle - Math.PI * 3) * 0.15;
        }

        add('camLobe', 'valvetrain', `Intake Cam Lobe ${idx + 1}`, [cx, camY, 0.32], [camAngle + idx * Math.PI * 0.5, 0, Math.PI / 2], [1, 1, 1], forgedSteel, { metallic: 0.9 });
        add('camLobe', 'valvetrain', `Exhaust Cam Lobe ${idx + 1}`, [cx, camY, -0.32], [camAngle + idx * Math.PI * 0.5 + Math.PI * 0.5, 0, Math.PI / 2], [1, 1, 1], forgedSteel, { metallic: 0.9 });

        // Intake Valve & Compressing Spring
        add('valve', 'valvetrain', `Intake Valve ${idx + 1}`, [cx, headY + 0.38 - intakeLift, 0.32], [0, 0, 0], [1, 1, 1], hexColor('#9eb0a0'), { metallic: 0.9, pick: true });
        const inSpringH = Math.max(0.24, 0.42 - intakeLift);
        add('spring', 'valvetrain', `Intake Spring ${idx + 1}`, [cx, headY + 0.30 - intakeLift * 0.5, 0.32], [0, 0, 0], [1, inSpringH / 0.42, 1], springSteel, {
          metallic: 0.85,
          leadLabel: idx === 0 ? 'Helical Valve Spring' : null
        });

        // Exhaust Valve & Compressing Spring
        const exValveColor = thermal ? exhaustThermal : hexColor('#9e8275');
        add('valve', 'valvetrain', `Exhaust Valve ${idx + 1}`, [cx, headY + 0.38 - exhaustLift, -0.32], [0, 0, 0], [1, 1, 1], exValveColor, { metallic: 0.85, glow: thermal ? 0.4 : 0, pick: true });
        const exSpringH = Math.max(0.24, 0.42 - exhaustLift);
        add('spring', 'valvetrain', `Exhaust Spring ${idx + 1}`, [cx, headY + 0.30 - exhaustLift * 0.5, -0.32], [0, 0, 0], [1, exSpringH / 0.42, 1], springSteel, { metallic: 0.85 });

        add('cylinder', 'fuel', `Fuel Injector ${idx + 1}`, [cx, headY + 0.52, 0], [0, 0, 0], [0.12, 0.12, 0.45], fuelColor, { metallic: 0.8, glow: 0.25, pick: true });
      });

      // 5. Common Rail High-Pressure Fuel System
      const railY = headY + 0.78 + explosion * 0.4;
      add('cylinder', 'fuel', 'Common Rail Manifold', [0, railY, 0], [0, 0, Math.PI / 2], [0.14, 0.14, 4.4], fuelColor, { metallic: 0.9, glow: 0.35, pick: true, leadLabel: 'Common-Rail Injection' });
      cylXs.forEach((cx, idx) => {
        add('cylinder', 'fuel', `High-Pressure Feed Line ${idx + 1}`, [cx, railY - 0.14, 0], [0, 0, 0], [0.04, 0.04, 0.28], fuelColor, { metallic: 0.8 });
      });

      // 6. Cast Aluminum Intake Plenum
      const intakeZ = 0.95 + explosion * 1.4;
      add('cylinder', 'turbo', 'Intake Plenum Chamber', [0, headY + 0.20, intakeZ], [0, 0, Math.PI / 2], [0.38, 0.38, 4.6], intakeAlum, { alpha: 0.85, metallic: 0.7, pick: true });
      cylXs.forEach(cx => {
        add('cylinder', 'turbo', 'Intake Runner', [cx, headY + 0.10, intakeZ * 0.55], [Math.PI * 0.25, 0, 0], [0.18, 0.18, 0.65], intakeAlum, { metallic: 0.7 });
      });

      // 7. Tuned Exhaust Header & Turbocharger
      const exhaustZ = -0.95 - explosion * 1.4;
      cylXs.forEach(cx => {
        add('cylinder', 'turbo', 'Exhaust Primary Pipe', [cx, headY - 0.10, exhaustZ * 0.55], [-Math.PI * 0.25, 0, 0], [0.18, 0.18, 0.65], exhaustThermal, { metallic: 0.6, glow: thermal ? 0.6 : 0 });
      });
      add('cylinder', 'turbo', 'Exhaust Collector Log', [0.6, headY - 0.35, exhaustZ], [0, 0, Math.PI / 2], [0.34, 0.34, 3.2], exhaustThermal, { metallic: 0.6, glow: thermal ? 0.7 : 0 });

      // Turbocharger
      const turboPos = [2.45 + explosion * 1.5, headY - 0.25, -0.95];
      add('torus', 'turbo', 'Turbo Turbine Housing', turboPos, [0, Math.PI / 2, 0], [0.75, 0.75, 0.75], exhaustThermal, { metallic: 0.5, glow: thermal ? 0.8 : 0, pick: true, leadLabel: 'Turbocharger' });
      add('torus', 'turbo', 'Turbo Compressor Housing', [turboPos[0] + 0.55, turboPos[1], turboPos[2]], [0, Math.PI / 2, 0], [0.82, 0.82, 0.82], castAlum, { metallic: 0.8, pick: true });
      add('impeller', 'turbo', 'Turbo Compressor Impeller', [turboPos[0] + 0.55, turboPos[1], turboPos[2]], [0, 0, this.turboAngle], [1, 1, 1], polishedSteel, { metallic: 0.95 });
      add('cylinder', 'turbo', 'Turbo Center Bearing Cartridge', [turboPos[0] + 0.28, turboPos[1], turboPos[2]], [0, 0, Math.PI / 2], [0.28, 0.28, 0.35], darkBlock, { metallic: 0.6 });
      add('cylinder', 'turbo', 'Wastegate Actuator', [turboPos[0] - 0.45, turboPos[1] + 0.35, turboPos[2]], [0, Math.PI * 0.25, Math.PI / 2], [0.18, 0.18, 0.45], forgedSteel, { metallic: 0.8 });

      // 8. Lubrication System: Ribbed Sump, Filter & Galleries
      const sumpY = -1.15 - explosion * 1.2;
      add('cube', 'lubrication', 'Oil Sump Pan', [0, sumpY, 0], [0, 0, 0], [4.6, 0.52, 1.5], castAlum, { alpha: this.xray ? 0.35 : 1.0, metallic: 0.5, pick: true, leadLabel: 'Ribbed Oil Sump' });
      for (let fin = -1.8; fin <= 1.8; fin += 0.4) {
        add('cube', 'lubrication', 'Sump Cooling Fin', [fin, sumpY - 0.28, 0], [0, 0, 0], [0.04, 0.12, 1.4], darkBlock, { alpha: this.xray ? 0.3 : 1.0 });
      }
      add('cylinder', 'lubrication', 'Spin-On Oil Filter', [-1.8, sumpY + 0.25, 0.95], [Math.PI * 0.35, 0, 0], [0.38, 0.38, 0.65], oilColor, { metallic: 0.85, glow: 0.2, pick: true });
      add('cylinder', 'lubrication', 'Main Oil Gallery Line', [0, -0.32, 0.75], [0, 0, Math.PI / 2], [0.08, 0.08, 4.4], oilColor, { metallic: 0.8, glow: 0.3 });

      const flowSpeed = Math.max(0.15, t.oilPressure / 50);
      for (let p = 0; p < 8; p += 1) {
        const px = (((time * 0.0008 * flowSpeed + p / 8) % 1) * 4.4) - 2.2;
        add('sphere', 'lubrication', 'Oil Flow Tracer', [px, -0.32, 0.75], [0, 0, 0], [0.09, 0.09, 0.09], oilColor, { glow: 0.85 });
      }

      // 9. Propeller Reduction Gearbox
      const gbX = -2.85 - explosion * 1.5;
      add('cylinder', 'propeller', 'Reduction Gearbox Casing', [gbX, 0.18, 0], [0, 0, Math.PI / 2], [0.95, 0.95, 0.72], castAlum, { metallic: 0.65, pick: true });
      add('cylinder', 'propeller', 'Propeller Drive Flange', [gbX - 0.45, 0.18, 0], [0, 0, Math.PI / 2], [0.65, 0.65, 0.18], polishedSteel, { metallic: 0.95, pick: true });
      add('cylinder', 'propeller', 'Propeller Spinner Dome', [gbX - 0.85, 0.18, 0], [0, 0, Math.PI / 2], [0.15, 0.58, 0.65], polishedSteel, { metallic: 0.9 });
      const propAngle = this.crankAngle * 0.46;
      for (let b = 0; b < 3; b += 1) {
        const bAngle = propAngle + (b * Math.PI * 2) / 3;
        add('cube', 'propeller', `Propeller Blade ${b + 1}`, [gbX - 0.75, 0.18 + Math.cos(bAngle) * 1.8, Math.sin(bAngle) * 1.8], [bAngle, 0, 0], [0.12, 3.4, 0.24], hexColor('#2a382c'), { metallic: 0.3 });
      }

      // 10. Electrical Alternator & FADEC ECU
      const altPos = [1.6 + explosion * 1.2, -0.65 - explosion * 0.5, 0.95 + explosion * 0.6];
      add('cylinder', 'electrical', '28V Alternator Body', altPos, [0, 0, Math.PI / 2], [0.85, 0.85, 0.95], electricColor, { metallic: 0.8, glow: electricColor === red ? 0.9 : 0.15, pick: true });
      add('cylinder', 'electrical', 'Alternator Pulley', [altPos[0] - 0.55, altPos[1], altPos[2]], [0, 0, Math.PI / 2], [0.38, 0.38, 0.14], polishedSteel, { metallic: 0.9 });

      const fadecPos = [-0.6, headY + 0.95 + explosion * 0.8, -0.85];
      add('cube', 'electrical', 'FADEC Dual-Channel ECU', fadecPos, [0, 0, 0], [1.4, 0.42, 0.65], darkBlock, { metallic: 0.7, pick: true, leadLabel: 'FADEC ECU' });

      return parts;
    }

    drawPart(part) {
      const gl = this.gl;
      const mesh = this.meshes[part.mesh];
      if (!mesh) return;

      const selected = this.selected === part.component ? 1 : 0;
      gl.bindBuffer(gl.ARRAY_BUFFER, mesh.position);
      gl.enableVertexAttribArray(this.locations.position);
      gl.vertexAttribPointer(this.locations.position, 3, gl.FLOAT, false, 0, 0);

      gl.bindBuffer(gl.ARRAY_BUFFER, mesh.normal);
      gl.enableVertexAttribArray(this.locations.normal);
      gl.vertexAttribPointer(this.locations.normal, 3, gl.FLOAT, false, 0, 0);

      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, mesh.index);

      gl.uniformMatrix4fv(this.locations.model, false, compose(part.position, part.rotation, part.scale));
      gl.uniform3fv(this.locations.color, part.color);
      gl.uniform1f(this.locations.alpha, part.alpha);
      gl.uniform1f(this.locations.glow, part.glow);
      gl.uniform1f(this.locations.selected, selected);
      gl.uniform1f(this.locations.metallic, part.metallic);
      gl.uniform1f(this.locations.roughness, part.roughness);

      if (part.alpha < 0.95) {
        gl.disable(gl.CULL_FACE);
      } else {
        gl.enable(gl.CULL_FACE);
      }

      gl.drawElements(gl.TRIANGLES, mesh.count, gl.UNSIGNED_SHORT, 0);
    }

    buildPickTargets(parts, viewProjection) {
      const rect = this.canvas.getBoundingClientRect();
      const seen = new Set();
      this.pickTargets = [];
      this.labelNodes = [];

      parts.forEach(part => {
        if (part.pick && !seen.has(part.component)) {
          seen.add(part.component);
          const pt = transformPoint(viewProjection, part.position);
          if (pt[2] >= -1 && pt[2] <= 1) {
            this.pickTargets.push({
              component: part.component,
              x: (pt[0] * 0.5 + 0.5) * rect.width,
              y: (1 - (pt[1] * 0.5 + 0.5)) * rect.height,
              radius: 38
            });
          }
        }
        if (part.leadLabel) {
          const pt = transformPoint(viewProjection, part.position);
          if (pt[2] >= -1 && pt[2] <= 1) {
            this.labelNodes.push({
              label: part.leadLabel,
              component: part.component,
              x: (pt[0] * 0.5 + 0.5) * rect.width,
              y: (1 - (pt[1] * 0.5 + 0.5)) * rect.height,
              worldZ: pt[2]
            });
          }
        }
      });
    }

    // --- Render 3D Leader-Line Labels ---
    drawLabelsOverlay() {
      if (!this.labelsCtx || !this.showLabels) {
        if (this.labelsCtx) this.labelsCtx.clearRect(0, 0, this.labelsCanvas.width, this.labelsCanvas.height);
        return;
      }
      const ctx = this.labelsCtx;
      const w = this.labelsCanvas.width;
      const h = this.labelsCanvas.height;
      const dpr = Math.min(window.devicePixelRatio || 1, 2.5);
      ctx.clearRect(0, 0, w, h);
      ctx.save();
      ctx.scale(dpr, dpr);

      this.labelNodes.slice(0, 6).forEach((node, idx) => {
        const isSelected = this.selected === node.component;
        const color = isSelected ? '#5eb574' : '#889c8a';
        const nx = node.x / dpr;
        const ny = node.y / dpr;

        const side = nx > (w / dpr) * 0.5 ? 1 : -1;
        const targetX = nx + side * 45;
        const targetY = ny - 25 - (idx % 3) * 12;

        ctx.beginPath();
        ctx.arc(nx, ny, 3, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();

        ctx.beginPath();
        ctx.moveTo(nx, ny);
        ctx.lineTo(targetX - side * 15, targetY);
        ctx.lineTo(targetX + side * 40, targetY);
        ctx.strokeStyle = isSelected ? 'rgba(94, 181, 116, 0.85)' : 'rgba(136, 156, 138, 0.45)';
        ctx.lineWidth = 1;
        ctx.stroke();

        ctx.font = '700 8.5px Inter, monospace';
        ctx.fillStyle = isSelected ? '#eaf5eb' : '#a8bfa9';
        ctx.textAlign = side > 0 ? 'left' : 'right';
        ctx.fillText(node.label.toUpperCase(), targetX + side * (side > 0 ? -10 : 35), targetY - 4);
      });
      ctx.restore();
    }

    // --- Render Synchronized 2D Kinematic Vector Diagram ---
    drawKinematicsDiagram() {
      if (!this.kinematicsCanvas) return;
      const canvas = this.kinematicsCanvas;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      const w = canvas.width, h = canvas.height;
      ctx.clearRect(0, 0, w, h);

      const cx = w * 0.28, cy = h * 0.52;
      const r = 26;
      const L = 68;

      const cylOffsets = [0, Math.PI * 3, Math.PI * 1, Math.PI * 2];
      const phi = (this.crankAngle + cylOffsets[this.activeCylinder]) % (Math.PI * 2);
      const px = cx + Math.sin(phi) * r;
      const py = cy - Math.cos(phi) * r;

      const pistonDisplacement = Math.cos(phi) * r + Math.sqrt(L * L - Math.pow(Math.sin(phi) * r, 2));
      const pistonX = cx + L + r - pistonDisplacement * 0.75 + 15;
      const pistonY = cy;

      // Crank Circle
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(94, 181, 116, 0.25)';
      ctx.lineWidth = 1;
      if (ctx.setLineDash) ctx.setLineDash([2, 2]);
      ctx.stroke();
      if (ctx.setLineDash) ctx.setLineDash([]);

      // Crank Center
      ctx.beginPath();
      ctx.arc(cx, cy, 3, 0, Math.PI * 2);
      ctx.fillStyle = '#5eb574';
      ctx.fill();

      // Crank Throw Vector
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(px, py);
      ctx.strokeStyle = '#5eb574';
      ctx.lineWidth = 2.5;
      ctx.stroke();

      // Crank Pin
      ctx.beginPath();
      ctx.arc(px, py, 3.5, 0, Math.PI * 2);
      ctx.fillStyle = '#fff';
      ctx.fill();

      // Connecting Rod Vector
      ctx.beginPath();
      ctx.moveTo(px, py);
      ctx.lineTo(pistonX, pistonY);
      ctx.strokeStyle = '#8a988c';
      ctx.lineWidth = 2;
      ctx.stroke();

      // Wrist Pin
      ctx.beginPath();
      ctx.arc(pistonX, pistonY, 3, 0, Math.PI * 2);
      ctx.fillStyle = '#4cb574';
      ctx.fill();

      // Piston Head Box
      ctx.fillStyle = 'rgba(194, 209, 197, 0.2)';
      ctx.strokeStyle = '#c2d1c5';
      ctx.lineWidth = 1.5;
      ctx.fillRect(pistonX - 4, pistonY - 14, 18, 28);
      ctx.strokeRect(pistonX - 4, pistonY - 14, 18, 28);

      // Kinematic Formula & Angle Readout
      ctx.font = '700 8px Inter, monospace';
      ctx.fillStyle = '#889c8a';
      ctx.textAlign = 'left';
      ctx.fillText(`θ = ${Math.round((phi * RAD) % 360)}° · STROKE ${(pistonDisplacement * 0.45).toFixed(1)}mm`, 8, 12);
      ctx.fillStyle = '#5eb574';
      ctx.fillText('x = r·cosθ + √(l² - r²sin²θ)', 8, h - 6);
    }

    // --- Render Synchronized Valve Timing & Piston Lift Graph ---
    drawValveTimingDiagram() {
      if (!this.valveCanvas) return;
      const canvas = this.valveCanvas;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      const w = canvas.width, h = canvas.height;
      ctx.clearRect(0, 0, w, h);

      const padL = 20, padR = 10, padT = 12, padB = 16;
      const graphW = w - padL - padR;
      const graphH = h - padT - padB;

      const strokes = ['IN', 'CMP', 'PWR', 'EXH'];
      for (let s = 0; s < 4; s++) {
        const sx = padL + (s / 4) * graphW;
        ctx.strokeStyle = 'rgba(255,255,255,0.06)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(sx, padT);
        ctx.lineTo(sx, padT + graphH);
        ctx.stroke();

        ctx.font = '700 7px Inter, monospace';
        ctx.fillStyle = 'rgba(136, 156, 138, 0.6)';
        ctx.textAlign = 'center';
        ctx.fillText(strokes[s], sx + (graphW / 8), padT + 8);
      }

      // Draw Piston Motion Curve (0-720 deg)
      ctx.beginPath();
      for (let i = 0; i <= 100; i++) {
        const frac = i / 100;
        const angle = frac * Math.PI * 4;
        const phi = angle % (Math.PI * 2);
        const yNorm = (Math.cos(phi) * 0.48 + Math.sqrt(1.35 * 1.35 - Math.pow(0.48 * Math.sin(phi), 2)) - 0.87) / 0.96;
        const gx = padL + frac * graphW;
        const gy = padT + graphH - yNorm * (graphH * 0.75);
        if (i === 0) ctx.moveTo(gx, gy);
        else ctx.lineTo(gx, gy);
      }
      ctx.strokeStyle = 'rgba(194, 209, 197, 0.35)';
      if (ctx.setLineDash) ctx.setLineDash([2, 2]);
      ctx.lineWidth = 1;
      ctx.stroke();
      if (ctx.setLineDash) ctx.setLineDash([]);

      // Draw Intake Valve Lift Curve (0 to 180 deg)
      ctx.beginPath();
      for (let i = 0; i <= 25; i++) {
        const frac = i / 100;
        const angle = frac * Math.PI * 4;
        const lift = Math.sin(angle) * (graphH * 0.7);
        const gx = padL + frac * graphW;
        const gy = padT + graphH - lift;
        if (i === 0) ctx.moveTo(gx, gy);
        else ctx.lineTo(gx, gy);
      }
      ctx.strokeStyle = '#5eb574';
      ctx.lineWidth = 1.8;
      ctx.stroke();

      // Draw Exhaust Valve Lift Curve (540 to 720 deg)
      ctx.beginPath();
      for (let i = 75; i <= 100; i++) {
        const frac = i / 100;
        const angle = frac * Math.PI * 4;
        const lift = Math.sin(angle - Math.PI * 3) * (graphH * 0.7);
        const gx = padL + frac * graphW;
        const gy = padT + graphH - lift;
        if (i === 75) ctx.moveTo(gx, gy);
        else ctx.lineTo(gx, gy);
      }
      ctx.strokeStyle = '#e85d3a';
      ctx.lineWidth = 1.8;
      ctx.stroke();

      // Live Tracking Cursor Line
      const cylOffsets = [0, Math.PI * 3, Math.PI * 1, Math.PI * 2];
      const cylCycle = (this.crankAngle + cylOffsets[this.activeCylinder]) % (Math.PI * 4);
      const cursorX = padL + (cylCycle / (Math.PI * 4)) * graphW;

      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(cursorX, padT);
      ctx.lineTo(cursorX, padT + graphH);
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(cursorX, padT + graphH, 3, 0, Math.PI * 2);
      ctx.fillStyle = '#5eb574';
      ctx.fill();

      ctx.font = '700 7px Inter, monospace';
      ctx.fillStyle = '#5eb574';
      ctx.textAlign = 'left';
      ctx.fillText('INTAKE', padL + 2, padT + graphH - 2);
      ctx.fillStyle = '#e85d3a';
      ctx.textAlign = 'right';
      ctx.fillText('EXHAUST', w - padR - 2, padT + graphH - 2);
    }

    // --- Render Synchronized P-V Indicator Diagram ---
    drawPressureDiagram() {
      if (!this.pressureCanvas) return;
      const canvas = this.pressureCanvas;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      const w = canvas.width, h = canvas.height;
      ctx.clearRect(0, 0, w, h);

      const padL = 22, padR = 10, padT = 12, padB = 16;
      const graphW = w - padL - padR;
      const graphH = h - padT - padB;

      ctx.strokeStyle = 'rgba(255,255,255,0.1)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(padL, padT);
      ctx.lineTo(padL, padT + graphH);
      ctx.lineTo(padL + graphW, padT + graphH);
      ctx.stroke();

      ctx.font = '700 7px Inter, monospace';
      ctx.fillStyle = 'rgba(136, 156, 138, 0.6)';
      ctx.textAlign = 'left';
      ctx.fillText('P (bar)', 2, padT + 6);
      ctx.textAlign = 'right';
      ctx.fillText('V (cm³)', w - 2, h - 2);

      function getPVPoint(theta) {
        const cycle = theta % (Math.PI * 4);
        let V = 0, P = 1.0;
        if (cycle < Math.PI) {
          const t = cycle / Math.PI;
          V = lerp(0.15, 0.95, t);
          P = 1.0;
        } else if (cycle < Math.PI * 2) {
          const t = (cycle - Math.PI) / Math.PI;
          V = lerp(0.95, 0.15, t);
          P = 1.0 * Math.pow(0.95 / V, 1.35);
        } else if (cycle < Math.PI * 3) {
          const t = (cycle - Math.PI * 2) / Math.PI;
          V = lerp(0.15, 0.95, t);
          const maxP = 38.0;
          P = maxP * Math.pow(0.15 / V, 1.30);
        } else {
          const t = (cycle - Math.PI * 3) / Math.PI;
          V = lerp(0.95, 0.15, t);
          P = 1.2;
        }
        return { V, P };
      }

      ctx.beginPath();
      for (let i = 0; i <= 100; i++) {
        const th = (i / 100) * Math.PI * 4;
        const pt = getPVPoint(th);
        const gx = padL + pt.V * graphW;
        const gy = padT + graphH - (pt.P / 42.0) * graphH;
        if (i === 0) ctx.moveTo(gx, gy);
        else ctx.lineTo(gx, gy);
      }
      if (ctx.closePath) ctx.closePath();
      ctx.fillStyle = 'rgba(232, 93, 58, 0.08)';
      ctx.fill();
      ctx.strokeStyle = '#e85d3a';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      const cylOffsets = [0, Math.PI * 3, Math.PI * 1, Math.PI * 2];
      const curAngle = (this.crankAngle + cylOffsets[this.activeCylinder]) % (Math.PI * 4);
      const curPt = getPVPoint(curAngle);
      const curGx = padL + curPt.V * graphW;
      const curGy = padT + graphH - (curPt.P / 42.0) * graphH;

      ctx.beginPath();
      ctx.arc(curGx, curGy, 4, 0, Math.PI * 2);
      ctx.fillStyle = '#5eb574';
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      ctx.font = '700 8px Inter, monospace';
      ctx.fillStyle = '#eaf5eb';
      ctx.textAlign = 'right';
      ctx.fillText(`${curPt.P.toFixed(1)} bar`, w - padR - 2, padT + 8);
    }

    frame(time) {
      const delta = Math.min(0.05, (time - this.lastTime) / 1000);
      this.lastTime = time;
      this.resize();

      if (!this.isPaused && !this.reducedMotion) {
        const rawRpm = Number(this.simRpm) || 0;
        if (rawRpm > 0) {
          const revsPerSec = clamp(rawRpm / 60, 0, 110);
          this.crankAngle = (this.crankAngle + delta * revsPerSec * Math.PI * 2 * this.playbackSpeed) % (Math.PI * 4);
          this.turboAngle = (this.turboAngle + delta * revsPerSec * Math.PI * 2 * 1.8 * this.playbackSpeed) % (Math.PI * 2);
          this.syncScrubber();
        }
      }

      this.explodeAmount += ((this.exploded ? 1.0 : 0.0) - this.explodeAmount) * Math.min(1.0, delta * 5.5);

      const gl = this.gl;
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);

      const rect = this.canvas.getBoundingClientRect();
      const aspect = Math.max(0.2, rect.width / Math.max(1, rect.height));
      const projection = mat4Perspective(36 * DEG, aspect, 0.1, 100);

      const cam = this.camera;
      const horiz = Math.cos(cam.pitch) * cam.distance;
      const eye = [
        cam.target[0] + Math.sin(cam.yaw) * horiz,
        cam.target[1] + Math.sin(cam.pitch) * cam.distance,
        cam.target[2] + Math.cos(cam.yaw) * horiz
      ];
      const view = mat4LookAt(eye, cam.target, [0, 1, 0]);

      gl.useProgram(this.program);
      gl.uniformMatrix4fv(this.locations.view, false, view);
      gl.uniformMatrix4fv(this.locations.projection, false, projection);

      const vibration = this.mode === 'vibration' ? clamp((this.telemetry.vibration - 0.7) * 0.016, 0, 0.08) : 0;
      const fault = this.telemetry.fault.toLowerCase();
      const faultShake = fault.includes('misfire') || fault.includes('knock') ? 0.04 : 0;
      const shift = [
        Math.sin(time * 0.055) * (vibration + faultShake),
        Math.cos(time * 0.045) * vibration,
        0
      ];

      const parts = this.buildParts(time);
      parts.forEach(part => {
        part.position = [
          part.position[0] + shift[0],
          part.position[1] + shift[1],
          part.position[2] + shift[2]
        ];
      });

      const opaque = parts.filter(p => p.alpha >= 0.95);
      const translucent = parts.filter(p => p.alpha < 0.95);

      gl.depthMask(true);
      opaque.forEach(p => this.drawPart(p));

      gl.depthMask(false);
      translucent.forEach(p => this.drawPart(p));
      gl.depthMask(true);

      const viewProj = mat4Multiply(projection, view);
      this.buildPickTargets(parts, viewProj);
      this.drawLabelsOverlay();
      this.drawKinematicsDiagram();
      this.drawValveTimingDiagram();
      this.drawPressureDiagram();

      requestAnimationFrame(next => this.frame(next));
    }
  }

  function showFallback(error) {
    const shell = document.querySelector ? document.querySelector('.engine-viewport') : document.getElementById('engineCanvas');
    if (!shell) return;
    shell.innerHTML = `<div class="engine-fallback" style="color:#e85d3a; padding:20px; text-align:center;"><strong>3D Engine Fallback Active</strong><br>${error.message}</div>`;
  }

  function init() {
    const canvas = document.getElementById('engineCanvas');
    const labelsCanvas = document.getElementById('engineLabelsCanvas');
    if (!canvas) return;
    try {
      const simulator = new AeroEngineSimulator(canvas, labelsCanvas);
      window.AeroPulseEngine3D = {
        setTelemetry: data => simulator.setTelemetry(data || {}),
        setMode: mode => simulator.setMode(mode),
        resetCamera: () => simulator.resetCamera(),
        setCameraPreset: p => simulator.setCameraPreset(p),
        resize: () => simulator.resize(),
        simulator
      };
      simulator.updateHud();
    } catch (error) {
      console.error('AeroPulse WebGL initialization failed:', error);
      showFallback(error);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();
