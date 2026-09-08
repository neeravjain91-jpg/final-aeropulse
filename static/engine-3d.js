/*
 * AeroPulse-X WebGL 3D Piston Engine Digital Twin (Military GCS Theme - High Detail Cutaway)
 * -----------------------------------------------------------------------------------------
 * High-definition, hardware-accelerated WebGL engineering renderer for the
 * Inline 4-Cylinder, 4-Stroke Turbocharged Liquid-Cooled Aero-Piston Engine.
 *
 * Implements:
 * 1. Precision 4-stroke slider-crank kinematics (crankshaft, H-beam connecting rods, pistons)
 * 2. Dual Overhead Camshafts (DOHC) & 4-stroke poppet valve timing with compressing coil springs
 * 3. Cutaway cylinder block & crankcase revealing polished cylinder liners & moving rotating assembly
 * 4. Turbocharger with high-speed spinning compressor/turbine wheels & wastegate actuator
 * 5. Common-rail direct fuel injection system & 4-into-1 tuned exhaust header
 * 6. Ribbed oil sump, oil pump, spin-on filter, and dynamic lubrication flow galleries
 * 7. Multi-mode rendering: Normal, Thermal Heatmap, Vibration Displacement, X-Ray, Exploded View
 * 8. Real-time telemetry synchronization (RPM, CHT, EGT, Oil P/T, Fuel Flow, Vibration, Faults)
 * 9. Sharp multi-light Blinn-Phong specular shader with zero haze and crisp edge definition
 */
(function () {
  'use strict';

  const DEG = Math.PI / 180;
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
  const lerp = (a, b, t) => a + (b - a) * t;

  // --- 4x4 Matrix Mathematics ---
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
    const c = Math.cos(angle);
    const s = Math.sin(angle);
    return new Float32Array([
      1, 0, 0, 0,
      0, c, s, 0,
      0, -s, c, 0,
      0, 0, 0, 1
    ]);
  }

  function mat4RotationY(angle) {
    const c = Math.cos(angle);
    const s = Math.sin(angle);
    return new Float32Array([
      c, 0, -s, 0,
      0, 1, 0, 0,
      s, 0, c, 0,
      0, 0, 0, 1
    ]);
  }

  function mat4RotationZ(angle) {
    const c = Math.cos(angle);
    const s = Math.sin(angle);
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

  // --- Color Utilities ---
  function hexColor(hex) {
    const val = Number.parseInt(hex.replace('#', ''), 16);
    return [((val >> 16) & 255) / 255, ((val >> 8) & 255) / 255, (val & 255) / 255];
  }

  function mixColor(a, b, t) {
    return [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)];
  }

  function thermalColor(value, low, high) {
    const t = clamp((value - low) / (high - low), 0, 1);
    if (t < 0.3) return mixColor(hexColor('#52cf80'), hexColor('#72c988'), t / 0.3);
    if (t < 0.65) return mixColor(hexColor('#72c988'), hexColor('#d9a74a'), (t - 0.3) / 0.35);
    return mixColor(hexColor('#d9a74a'), hexColor('#e63946'), (t - 0.65) / 0.35);
  }

  // --- Procedural 3D Geometry Generators ---

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

    // Side wall
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
      indices.push(i0, i1, i2, i2, i1, i3);
    }

    // Top cap
    const topCenter = positions.length / 3;
    positions.push(0, halfH, 0);
    normals.push(0, 1, 0);
    for (let i = 0; i <= segments; i += 1) {
      const theta = (i / segments) * Math.PI * 2;
      positions.push(Math.cos(theta) * radiusTop, halfH, Math.sin(theta) * radiusTop);
      normals.push(0, 1, 0);
    }
    for (let i = 0; i < segments; i += 1) {
      indices.push(topCenter, topCenter + 1 + i, topCenter + 2 + i);
    }

    // Bottom cap
    const bottomCenter = positions.length / 3;
    positions.push(0, -halfH, 0);
    normals.push(0, -1, 0);
    for (let i = 0; i <= segments; i += 1) {
      const theta = (i / segments) * Math.PI * 2;
      positions.push(Math.cos(theta) * radiusBottom, -halfH, Math.sin(theta) * radiusBottom);
      normals.push(0, -1, 0);
    }
    for (let i = 0; i < segments; i += 1) {
      indices.push(bottomCenter, bottomCenter + 2 + i, bottomCenter + 1 + i);
    }

    return { positions, normals, indices };
  }

  function makeCutawayCylinder(segments = 24, startAngle = 0, endAngle = Math.PI * 1.25, innerR = 0.44, outerR = 0.54, height = 1.0) {
    const positions = [];
    const normals = [];
    const indices = [];
    const halfH = height * 0.5;

    // Outer wall
    const segCount = Math.max(4, Math.round(segments * ((endAngle - startAngle) / (Math.PI * 2))));
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
      indices.push(i0, i0 + 1, i0 + 2, i0 + 2, i0 + 1, i0 + 3);
    }

    // Inner wall (cutaway interior surface facing inward)
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
      indices.push(i0, i0 + 2, i0 + 1, i0 + 2, i0 + 3, i0 + 1);
    }

    // Cut face 1 (start angle cross section)
    const cut1Base = positions.length / 3;
    const cosS = Math.cos(startAngle), sinS = Math.sin(startAngle);
    const nCut1 = [-sinS, 0, cosS];
    positions.push(cosS * innerR, halfH, sinS * innerR);
    positions.push(cosS * outerR, halfH, sinS * outerR);
    positions.push(cosS * outerR, -halfH, sinS * outerR);
    positions.push(cosS * innerR, -halfH, sinS * innerR);
    for (let k = 0; k < 4; k++) normals.push(...nCut1);
    indices.push(cut1Base, cut1Base + 1, cut1Base + 2, cut1Base, cut1Base + 2, cut1Base + 3);

    // Cut face 2 (end angle cross section)
    const cut2Base = positions.length / 3;
    const cosE = Math.cos(endAngle), sinE = Math.sin(endAngle);
    const nCut2 = [sinE, 0, -cosE];
    positions.push(cosE * outerR, halfH, sinE * outerR);
    positions.push(cosE * innerR, halfH, sinE * innerR);
    positions.push(cosE * innerR, -halfH, sinE * innerR);
    positions.push(cosE * outerR, -halfH, sinE * outerR);
    for (let k = 0; k < 4; k++) normals.push(...nCut2);
    indices.push(cut2Base, cut2Base + 1, cut2Base + 2, cut2Base, cut2Base + 2, cut2Base + 3);

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
        indices.push(first, second, first + 1, second, second + 1, first + 1);
      }
    }
    return { positions, normals, indices };
  }

  function makeTorus(radialSegments = 24, tubularSegments = 14, radius = 0.5, tube = 0.14) {
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

      // Tangent vector
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
        indices.push(i0, i1, i2, i0, i2, i3);
      }
    }
    return { positions, normals, indices };
  }

  function makePiston() {
    // Detailed piston: crown, 3 compression ring lands, skirt with wrist pin bore
    const positions = [];
    const normals = [];
    const indices = [];
    const segs = 24;
    const r = 0.42;
    const h = 0.52;

    // Crown cap with slight combustion bowl depression
    const centerIdx = positions.length / 3;
    positions.push(0, h * 0.5 - 0.04, 0); // Dish center
    normals.push(0, 1, 0);
    for (let i = 0; i <= segs; i += 1) {
      const th = (i / segs) * Math.PI * 2;
      positions.push(Math.cos(th) * r, h * 0.5, Math.sin(th) * r);
      normals.push(0, 1, 0);
    }
    for (let i = 0; i < segs; i += 1) {
      indices.push(centerIdx, centerIdx + 1 + i, centerIdx + 2 + i);
    }

    // Cylindrical piston skirt with 3 ring groove ridges
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
        indices.push(base0 + i, base1 + i, base0 + i + 1, base0 + i + 1, base1 + i, base1 + i + 1);
      }
    }

    return { positions, normals, indices };
  }

  function makeConnectingRod() {
    // Detailed forged H-beam connecting rod
    const positions = [];
    const normals = [];
    const indices = [];

    // Helper: add a box to this mesh
    function addBox(x, y, z, w, h, d, normOverride = null) {
      const b = makeCube();
      const base = positions.length / 3;
      for (let i = 0; i < b.positions.length; i += 3) {
        positions.push(
          b.positions[i] * w + x,
          b.positions[i + 1] * h + y,
          b.positions[i + 2] * d + z
        );
        if (normOverride) {
          normals.push(...normOverride);
        } else {
          normals.push(b.normals[i], b.normals[i + 1], b.normals[i + 2]);
        }
      }
      for (let i = 0; i < b.indices.length; i++) {
        indices.push(base + b.indices[i]);
      }
    }

    // 1. Central I-Beam shank (web + 2 flanges)
    addBox(0, 0, 0, 0.08, 1.05, 0.04);       // Central Web
    addBox(0, 0, 0.045, 0.09, 1.05, 0.03);   // Front Flange
    addBox(0, 0, -0.045, 0.09, 1.05, 0.03);  // Rear Flange

    // 2. Big-end eye (surrounds crank journal)
    addBox(0, -0.55, 0, 0.16, 0.22, 0.18);
    // 3. Small-end eye (surrounds wrist pin)
    addBox(0, 0.55, 0, 0.12, 0.16, 0.14);

    return { positions, normals, indices };
  }

  function makeCrankshaftWeb() {
    // Contoured counterbalance lobe for crankshaft
    const positions = [];
    const normals = [];
    const indices = [];
    const segs = 12;
    const r = 0.52;
    const thick = 0.11;

    // Fan-shaped counterweight covering 140 degrees
    const baseIdx = 0;
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
      indices.push(0, f0, f1);         // Front cap
      indices.push(1, f1 + 1, f0 + 1); // Rear cap
    }

    // Outer rim
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
    // Poppet valve: beveled 45-deg head + stem + retainer groove
    const positions = [];
    const normals = [];
    const indices = [];
    const segs = 18;
    const headR = 0.22;
    const stemR = 0.038;
    const stemH = 0.72;

    // Beveled head bottom
    const centerB = positions.length / 3;
    positions.push(0, -0.04, 0);
    normals.push(0, -1, 0);
    for (let i = 0; i <= segs; i += 1) {
      const th = (i / segs) * Math.PI * 2;
      positions.push(Math.cos(th) * headR, 0, Math.sin(th) * headR);
      normals.push(Math.cos(th) * 0.7, -0.7, Math.sin(th) * 0.7);
    }
    for (let i = 0; i < segs; i += 1) {
      indices.push(centerB, centerB + 2 + i, centerB + 1 + i);
    }

    // Stem cylinder
    const stemBase = positions.length / 3;
    for (let i = 0; i <= segs; i += 1) {
      const th = (i / segs) * Math.PI * 2;
      const cosT = Math.cos(th);
      const sinT = Math.sin(th);
      positions.push(cosT * stemR, 0, sinT * stemR);
      positions.push(cosT * stemR, stemH, sinT * stemR);
      normals.push(cosT, 0, sinT);
      normals.push(cosT, 0, sinT);
    }
    for (let i = 0; i < segs; i += 1) {
      const i0 = stemBase + i * 2;
      indices.push(i0, i0 + 1, i0 + 2, i0 + 2, i0 + 1, i0 + 3);
    }

    return { positions, normals, indices };
  }

  function makeCamLobe() {
    // Eccentric egg-shaped cam lobe
    const positions = [];
    const normals = [];
    const indices = [];
    const segs = 20;
    const baseR = 0.12;
    const lift = 0.10;
    const width = 0.14;

    function getLobeRadius(angle) {
      const cosA = Math.cos(angle);
      return baseR + (cosA > 0 ? cosA * cosA * lift : 0);
    }

    const halfW = width * 0.5;
    // Front & rear faces
    positions.push(0, 0, halfW); // 0
    normals.push(0, 0, 1);
    positions.push(0, 0, -halfW); // 1
    normals.push(0, 0, -1);

    for (let i = 0; i <= segs; i += 1) {
      const th = (i / segs) * Math.PI * 2;
      const r = getLobeRadius(th);
      const x = Math.cos(th) * r;
      const y = Math.sin(th) * r;
      positions.push(x, y, halfW);
      normals.push(0, 0, 1);
      positions.push(x, y, -halfW);
      normals.push(0, 0, -1);
    }

    for (let i = 0; i < segs; i += 1) {
      const f0 = 2 + i * 2;
      const f1 = 2 + (i + 1) * 2;
      indices.push(0, f0, f1);
      indices.push(1, f1 + 1, f0 + 1);
    }

    // Outer perimeter
    const rimBase = positions.length / 3;
    for (let i = 0; i <= segs; i += 1) {
      const th = (i / segs) * Math.PI * 2;
      const r = getLobeRadius(th);
      const x = Math.cos(th) * r;
      const y = Math.sin(th) * r;
      positions.push(x, y, halfW);
      positions.push(x, y, -halfW);
      const nx = Math.cos(th);
      const ny = Math.sin(th);
      normals.push(nx, ny, 0);
      normals.push(nx, ny, 0);
    }
    for (let i = 0; i < segs; i += 1) {
      const i0 = rimBase + i * 2;
      indices.push(i0, i0 + 1, i0 + 2, i0 + 2, i0 + 1, i0 + 3);
    }

    return { positions, normals, indices };
  }

  function makeTurboImpeller(blades = 8) {
    // High-speed multi-blade compressor/turbine wheel
    const positions = [];
    const normals = [];
    const indices = [];

    // Central hub cone
    const c = makeCylinder(16, 0.08, 0.28, 0.22);
    positions.push(...c.positions);
    normals.push(...c.normals);
    indices.push(...c.indices);

    // Blades
    for (let b = 0; b < blades; b += 1) {
      const angle = (b / blades) * Math.PI * 2;
      const cosA = Math.cos(angle);
      const sinA = Math.sin(angle);
      const base = positions.length / 3;

      const rInner = 0.12;
      const rOuter = 0.38;
      const h0 = 0.08;
      const h1 = -0.08;

      positions.push(cosA * rInner, h0, sinA * rInner);
      positions.push(cosA * rOuter, h1, sinA * rOuter);
      positions.push(Math.cos(angle + 0.15) * rOuter, h1, Math.sin(angle + 0.15) * rOuter);
      positions.push(Math.cos(angle + 0.1) * rInner, h0, Math.sin(angle + 0.1) * rInner);

      const n = [-sinA, 0.4, cosA];
      for (let k = 0; k < 4; k++) normals.push(...n);
      indices.push(base, base + 1, base + 2, base, base + 2, base + 3);
    }

    return { positions, normals, indices };
  }

  // --- WebGL Shaders & Shader Program ---
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

        // 3-Point Precision Lighting Rig
        vec3 L1 = normalize(vec3(0.58, 0.82, 0.65));  // Primary Key Light (crisp upper-right)
        vec3 L2 = normalize(vec3(-0.65, 0.35, -0.5)); // Cool Fill Light (shadow relief)
        vec3 L3 = normalize(vec3(0.0, -0.85, 0.52));  // Under-engine Ground Bounce

        float diff1 = max(dot(N, L1), 0.0);
        float diff2 = max(dot(N, L2), 0.0) * 0.38;
        float diff3 = max(dot(N, L3), 0.0) * 0.18;
        float diffuse = diff1 + diff2 + diff3;

        // Blinn-Phong Specular Reflection for Polished Machined Metals
        vec3 H1 = normalize(L1 + V);
        float specPower = mix(16.0, 96.0, uMetallic);
        float specFactor = mix(0.20, 0.85, uMetallic);
        float spec = pow(max(dot(N, H1), 0.0), specPower) * specFactor;

        // Subtle Fresnel Rim Highlight
        float rim = pow(1.0 - max(dot(N, V), 0.0), 3.0);

        // Metallic Base & Ambient
        vec3 ambient = uColor * mix(0.26, 0.14, uMetallic);
        vec3 baseColor = ambient + uColor * (0.74 * diffuse) + vec3(0.92, 0.96, 0.94) * spec;

        // Selection & Localized Thermal/Alarm Glow
        baseColor += uColor * uGlow * 0.75;
        if (uSelected > 0.5) {
          baseColor += vec3(0.35, 0.88, 0.48) * (rim * 0.75 + 0.15);
        }

        gl_FragColor = vec4(baseColor, uAlpha);
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
  // Master AeroEngineRenderer Class
  // =========================================================================
  class AeroEngineRenderer {
    constructor(canvas) {
      this.canvas = canvas;
      this.gl = canvas.getContext('webgl', {
        antialias: true,
        alpha: true,
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

      // Upload High-Fidelity Geometry Buffers
      this.meshes = {
        cube: uploadMesh(this.gl, makeCube()),
        cylinder: uploadMesh(this.gl, makeCylinder(24)),
        cutawayCylinder: uploadMesh(this.gl, makeCutawayCylinder(24, 0, Math.PI * 1.25, 0.44, 0.54, 1.0)),
        sphere: uploadMesh(this.gl, makeSphere(14, 20)),
        torus: uploadMesh(this.gl, makeTorus(24, 14, 0.5, 0.12)),
        spring: uploadMesh(this.gl, makeHelicalSpring(4.5, 0.14, 0.03, 0.42)),
        piston: uploadMesh(this.gl, makePiston()),
        connectingRod: uploadMesh(this.gl, makeConnectingRod()),
        crankLobe: uploadMesh(this.gl, makeCrankshaftWeb()),
        valve: uploadMesh(this.gl, makePoppetValve()),
        camLobe: uploadMesh(this.gl, makeCamLobe()),
        impeller: uploadMesh(this.gl, makeTurboImpeller(8))
      };

      this.telemetry = {
        rpm: 0,
        throttle: 0,
        cht: 220,
        egt: 1200,
        oilPressure: 60,
        oilTemp: 85,
        fuelFlow: 20,
        vibration: 0.0,
        busVoltage: 28.2,
        health: 100,
        fault: 'none',
        engineState: 'ENGINE_OFF'
      };

      this.mode = 'normal';
      this.paused = false;
      this.xray = false;
      this.exploded = false;
      this.explodeAmount = 0;

      // 4-Stroke Cycle Crank Angle (0 to 4*PI radians = 720 degrees)
      this.crankAngle = 0;
      this.turboAngle = 0;

      // Optimal 3/4 Engineering Isometric Perspective
      this.camera = { yaw: -38 * DEG, pitch: 22 * DEG, distance: 10.5 };
      this.selected = 'crankcase';
      this.drag = null;
      this.pickTargets = [];
      this.lastTime = performance.now();
      this.reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

      this.configureGl();
      this.bindInteractions();
      this.bindControls();

      this.resizeObserver = new ResizeObserver(() => this.resize());
      if (canvas.parentElement) {
        this.resizeObserver.observe(canvas.parentElement);
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
      gl.clearColor(0.024, 0.042, 0.028, 1);
    }

    resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const rect = this.canvas.getBoundingClientRect();
      const width = Math.max(320, Math.round(rect.width * dpr));
      const height = Math.max(260, Math.round(rect.height * dpr));
      if (this.canvas.width !== width || this.canvas.height !== height) {
        this.canvas.width = width;
        this.canvas.height = height;
        this.gl.viewport(0, 0, width, height);
      }
    }

    resetCamera() {
      this.camera = { yaw: -38 * DEG, pitch: 22 * DEG, distance: 10.5 };
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
      const viewport = this.canvas.closest('.engine-viewport');
      if (viewport) {
        viewport.classList.toggle('thermal-active', this.mode === 'thermal');
        viewport.style.setProperty('--thermal-rgb', color.join(', '));
        viewport.style.setProperty('--thermal-level', level.toFixed(3));
      }
      const value = document.getElementById('engineThermalValue');
      if (value) value.textContent = `${Math.round(t.cht)}°F CHT · ${Math.round(t.egt).toLocaleString()}°F EGT`;
      const marker = document.getElementById('engineThermalMarker');
      if (marker) marker.style.left = `${Math.round(level * 100)}%`;
      const field = document.getElementById('engineThermalField');
      if (field) {
        const state = level >= 0.86 ? 'critical' : level >= 0.7 ? 'hot' : level >= 0.34 ? 'nominal' : 'cool';
        field.dataset.thermalState = state;
      }
    }

    updateHud() {
      const values = {
        engineHudRpm: `${Math.round(this.telemetry.rpm).toLocaleString()} RPM`,
        engineHudCht: `${Math.round(this.telemetry.cht)}°F CHT`,
        engineHudEgt: `${Math.round(this.telemetry.egt)}°F EGT`,
        engineHudOil: `${this.telemetry.oilPressure.toFixed(0)} PSI OIL`,
        engineHudVibration: `${this.telemetry.vibration.toFixed(2)} g RMS`
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
      const entries = {
        crankcase: ['Central Crankcase & Block', `${Math.round(t.rpm)} RPM`, `${t.vibration.toFixed(2)} g`, 'Inline-4 structural crankcase with cross-bolted main bearing caps'],
        cylinders: ['Cylinder Liners & Head', `${Math.round(t.cht)}°F CHT`, `${Math.round(t.egt)}°F EGT`, 'Cutaway liquid-cooled cylinder bank & combustion chambers'],
        pistons: ['Piston & Rod Assemblies', `${Math.round(t.rpm)} RPM`, '4-Stroke Kinematics', 'Machined aluminum pistons, 3-ring lands & forged H-beam connecting rods'],
        crankshaft: ['Crankshaft & Counterweights', `${Math.round(t.rpm)} RPM`, `${t.vibration.toFixed(2)} g`, 'Flat-plane 180° forged steel crankshaft with 8 balance counterweights'],
        valvetrain: ['DOHC Valvetrain & Springs', `${Math.round(t.rpm * 0.5)} RPM Cam`, '8-Poppet Valves', 'Dual overhead camshafts, intake/exhaust poppet valves & dynamic coil springs'],
        turbo: ['Turbocharger & Boost Circuit', `${Math.max(0.6, 0.55 + t.throttle / 100).toFixed(2)} bar Boost`, `${Math.round(t.egt)}°F Turbine`, 'High-pressure turbo compressor & exhaust gas energy recovery turbine'],
        fuel: ['Common-Rail Direct Injection', `${t.fuelFlow.toFixed(1)} L/h`, `${Math.round(t.throttle)}% Pulse`, 'High-pressure common-rail manifold & 4 solenoid injectors'],
        lubrication: ['Lubrication Circuit & Sump', `${t.oilPressure.toFixed(1)} PSI`, `${t.oilTemp.toFixed(1)}°C`, 'Ribbed oil sump, oil pump, spin-on filter & pressurized galleries'],
        propeller: ['Reduction Gearbox & Drive', `${Math.round(t.rpm * 0.46)} RPM Prop`, `${Math.round(t.throttle)}% Load`, 'Propeller reduction output drive shaft & hub flange'],
        electrical: ['Alternator & FADEC ECU', `${t.busVoltage.toFixed(1)} V Bus`, `${Math.round(t.health)}% Health`, '28V brushless alternator & FADEC dual-channel engine control unit'],
        sensors: ['Virtual Sensor Network', `${Math.round(t.health)}% Trust`, fault.includes('sensor') ? 'DRIFT' : 'TRUSTED', 'FADEC redundant sensor nodes (CHT, EGT, MAP, Oil P/T, Crank)']
      };
      return entries[component] || entries.crankcase;
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
        this.paused = !this.paused;
        event.currentTarget.classList.toggle('active', this.paused);
        event.currentTarget.textContent = this.paused ? 'Resume' : 'Pause';
      });
      on('engineXray', 'click', event => {
        this.xray = !this.xray;
        event.currentTarget.classList.toggle('active', this.xray);
      });
      on('engineExplode', 'click', event => {
        this.exploded = !this.exploded;
        event.currentTarget.classList.toggle('active', this.exploded);
      });
      document.querySelectorAll('[data-engine-mode]').forEach(button => {
        button.addEventListener('click', () => this.setMode(button.dataset.engineMode));
      });
    }

    bindInteractions() {
      this.canvas.addEventListener('pointerdown', event => {
        this.canvas.setPointerCapture(event.pointerId);
        this.drag = { x: event.clientX, y: event.clientY, startX: event.clientX, startY: event.clientY };
      });
      this.canvas.addEventListener('pointermove', event => {
        if (!this.drag) return;
        const dx = event.clientX - this.drag.x;
        const dy = event.clientY - this.drag.y;
        this.camera.yaw -= dx * 0.007;
        this.camera.pitch = clamp(this.camera.pitch - dy * 0.006, -1.15, 1.15);
        this.drag.x = event.clientX;
        this.drag.y = event.clientY;
      });
      this.canvas.addEventListener('pointerup', event => {
        if (!this.drag) return;
        const moved = Math.hypot(event.clientX - this.drag.startX, event.clientY - this.drag.startY);
        if (moved < 6) this.pick(event);
        this.drag = null;
      });
      this.canvas.addEventListener('wheel', event => {
        event.preventDefault();
        this.camera.distance = clamp(this.camera.distance + event.deltaY * 0.010, 6.0, 18.0);
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
        pick: options.pick ?? false
      };
    }

    // =========================================================================
    // Mechanical Scene Assembly (Inline-4 4-Stroke Cutaway Digital Twin)
    // =========================================================================
    buildParts(time) {
      const t = this.telemetry;
      const fault = t.fault.toLowerCase();
      const thermal = this.mode === 'thermal';
      const vibrationMode = this.mode === 'vibration';
      const explosion = this.explodeAmount;

      // Engineering Materials Palette
      const darkBlock = hexColor('#1e2820');        // Cast iron / structural block
      const castAlum = hexColor('#566458');         // Cast aluminum head / sump
      const polishedSteel = hexColor('#c2ccc4');    // Polished steel crankshaft / wrist pins
      const forgedSteel = hexColor('#8a988c');      // Forged con-rods / cams
      const brightAlum = hexColor('#9eb0a0');       // Machined aluminum pistons
      const bronze = hexColor('#bfa054');           // Bronze valve guides / bushings
      const exhaustIron = hexColor('#5a3825');      // Heat-treated exhaust headers / turbine
      const intakeAlum = hexColor('#629472');       // Anodized intake plenum & fuel rail
      const springSteel = hexColor('#a2aea4');      // High-tensile spring steel
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

      const housingAlpha = this.xray ? 0.20 : 1.0;
      const parts = [];
      const add = (...args) => parts.push(this.part(...args));

      // Inline-4 Geometry Parameters
      // 4 Cylinders positioned along X-axis: X = -1.80, -0.60, +0.60, +1.80
      const cylXs = [-1.80, -0.60, 0.60, 1.80];
      const crankR = 0.48; // Crank throw radius
      const rodL = 1.35;   // Connecting rod length

      // 4-Stroke Phase Angles (720-deg cycle): Firing order 1 - 3 - 4 - 2
      // Flat-plane crank throws: Cyl 1 (0), Cyl 2 (PI), Cyl 3 (PI), Cyl 4 (0)
      const cycleAngles = [
        (this.crankAngle + 0) % (Math.PI * 4),
        (this.crankAngle + Math.PI * 3) % (Math.PI * 4),
        (this.crankAngle + Math.PI * 1) % (Math.PI * 4),
        (this.crankAngle + Math.PI * 2) % (Math.PI * 4)
      ];

      // -----------------------------------------------------------------------
      // 1. Central Engine Block & Crankcase (Precision Cutaway Presentation)
      // -----------------------------------------------------------------------
      // Lower Crankcase Bedplate
      add('cube', 'crankcase', 'Crankcase Bedplate', [0, -0.45 - explosion * 0.35, 0], [0, 0, 0], [4.9, 0.45, 1.6], darkBlock, { alpha: housingAlpha, metallic: 0.4, pick: true });

      // Upper Cylinder Block (Cutaway section over Cylinders 1, 2, 3 to reveal inner motion)
      add('cube', 'crankcase', 'Block Rear Wall', [0, 0.85, -0.65], [0, 0, 0], [4.9, 1.8, 0.35], darkBlock, { alpha: housingAlpha, metallic: 0.3 });
      add('cube', 'crankcase', 'Block End Wall Front', [-2.45, 0.85, 0], [0, 0, 0], [0.35, 1.8, 1.5], darkBlock, { alpha: housingAlpha });
      add('cube', 'crankcase', 'Block End Wall Rear', [2.45, 0.85, 0], [0, 0, 0], [0.35, 1.8, 1.5], darkBlock, { alpha: housingAlpha });

      // Cylinder 4 Outer Wall & Water Jacket (Non-cutaway section showing ribbed outer cooling barrel)
      add('cylinder', 'cylinders', 'Cylinder 4 Outer Barrel', [1.80, 0.95, 0], [0, 0, 0], [1.08, 1.08, 1.65], cylinderThermal, { alpha: housingAlpha, metallic: 0.4, pick: true });
      add('torus', 'cylinders', 'Cooling Jacket Rib 1', [1.80, 0.70, 0], [Math.PI / 2, 0, 0], [1.14, 1.14, 0.16], darkBlock, { alpha: housingAlpha });
      add('torus', 'cylinders', 'Cooling Jacket Rib 2', [1.80, 1.20, 0], [Math.PI / 2, 0, 0], [1.14, 1.14, 0.16], darkBlock, { alpha: housingAlpha });

      // Polished Cylinder Liners (Cutaway cross-section bores for Cylinders 1, 2, 3)
      for (let i = 0; i < 3; i++) {
        add('cutawayCylinder', 'cylinders', `Cylinder Liner ${i + 1}`, [cylXs[i], 0.95, 0], [0, -Math.PI * 0.15, 0], [1.0, 1.65, 1.0], hexColor('#8e9c90'), { metallic: 0.8, roughness: 0.2, pick: true });
      }

      // -----------------------------------------------------------------------
      // 2. Crankshaft, Main Bearing Journals & Counterweights
      // -----------------------------------------------------------------------
      // 5 Main Bearing Journals along axis Y=0, Z=0
      const mainXs = [-2.40, -1.20, 0.0, 1.20, 2.40];
      mainXs.forEach((mx, idx) => {
        add('cylinder', 'crankshaft', `Main Journal ${idx + 1}`, [mx, 0, 0], [0, 0, Math.PI / 2], [0.36, 0.36, 0.32], polishedSteel, { metallic: 0.9, roughness: 0.15, pick: true });
        // Main bearing cap
        add('cube', 'crankcase', `Bearing Saddle ${idx + 1}`, [mx, -0.16, 0], [0, 0, 0], [0.26, 0.30, 0.65], darkBlock, { alpha: housingAlpha });
      });

      // 4 Crankpins & 8 Counterbalance Lobes
      cylXs.forEach((cx, idx) => {
        const phi = cycleAngles[idx] % (Math.PI * 2);
        const pinY = Math.cos(phi) * crankR;
        const pinZ = Math.sin(phi) * crankR;

        // Rod Crankpin Journal
        add('cylinder', 'crankshaft', `Crankpin ${idx + 1}`, [cx, pinY, pinZ], [0, 0, Math.PI / 2], [0.32, 0.32, 0.38], polishedSteel, { metallic: 0.95, roughness: 0.1, pick: true });

        // Left and right crank web counterweights
        [-0.22, 0.22].forEach(wOffset => {
          add('crankLobe', 'crankshaft', `Counterweight ${idx + 1}`, [cx + wOffset, 0, 0], [phi + Math.PI, 0, Math.PI / 2], [1.0, 1.0, 1.0], forgedSteel, { metallic: 0.7, roughness: 0.35 });
        });
      });

      // -----------------------------------------------------------------------
      // 3. Pistons, Wrist Pins & Connecting Rods (Exact 4-Stroke Slider-Crank with Piston Thermal Projection)
      // -----------------------------------------------------------------------
      cylXs.forEach((cx, idx) => {
        const cycle = cycleAngles[idx];
        const phi = cycle % (Math.PI * 2);

        // Exact slider-crank mathematical kinematics
        const pinY = Math.cos(phi) * crankR;
        const pinZ = Math.sin(phi) * crankR;
        const pistonY = pinY + Math.sqrt(rodL * rodL - (pinZ * pinZ));
        const rodAngle = Math.asin((pinZ) / rodL); // Tilt angle around X-axis

        const misfire = fault.includes('misfire') && idx === 1;
        const hotCyl = (fault.includes('overheat') || fault.includes('thermal')) && (idx === 1 || idx === 2);

        // Piston Localized Temperature Calculations
        const isCombustionStroke = cycle >= 0 && cycle < Math.PI;
        const powerProgress = isCombustionStroke ? Math.sin((cycle / Math.PI) * Math.PI) : 0;
        const strokeHeatBoost = isCombustionStroke && t.rpm > 200 ? powerProgress * 45 : 0;
        const cylCht = t.cht + (hotCyl ? 48 : (idx === 1 ? 8 : -4));
        const pistonCrownTemp = cylCht + 0.28 * Math.max(0, t.egt - cylCht) * (t.throttle / 100) + strokeHeatBoost;
        const crownHeatColor = thermalColor(pistonCrownTemp, 180, 315);
        const ring1Color = thermalColor(pistonCrownTemp * 0.88, 180, 315);
        const ring2Color = thermalColor(pistonCrownTemp * 0.76, 180, 315);
        const ring3Color = thermalColor(pistonCrownTemp * 0.64, 180, 315);

        const pColor = hotCyl ? red : thermal ? ring2Color : brightAlum;

        // Piston Body (Skirt & Wrist Pin Hub)
        add('piston', 'pistons', Piston , [cx, pistonY + 0.15, 0], [0, 0, 0], [1.0, 1.0, 1.0], pColor, { metallic: 0.85, roughness: 0.25, glow: misfire ? 0.6 : hotCyl ? 0.8 : (thermal ? 0.25 : 0), pick: true });

        // Steel Wrist Pin (Gudgeon Pin)
        add('cylinder', 'pistons', Wrist Pin , [cx, pistonY, 0], [0, 0, Math.PI / 2], [0.14, 0.14, 0.52], polishedSteel, { metallic: 0.95 });

        // Forged H-Beam Connecting Rod (pivots between crankpin and wrist pin)
        const rodMidY = (pinY + pistonY) * 0.5;
        const rodMidZ = pinZ * 0.5;
        const rodColor = thermal ? thermalColor(pistonCrownTemp * 0.55, 180, 315) : forgedSteel;
        add('connectingRod', 'pistons', Connecting Rod , [cx, rodMidY, rodMidZ], [-rodAngle, 0, 0], [1.0, 1.0, 1.0], rodColor, { metallic: 0.75, roughness: 0.3 });

        // =====================================================================
        // PISTON THERMAL PROJECTION & HEAT FLUX FIELD
        // =====================================================================
        // A. Piston Crown High-Temperature Core Disk
        const crownGlow = thermal ? (0.75 + powerProgress * 0.45) : (hotCyl ? 0.85 : 0.0);
        add('cylinder', 'pistons', Piston Crown Thermal Core , [cx, pistonY + 0.41, 0], [0, 0, 0], [0.80, 0.80, 0.04], crownHeatColor, {
          alpha: thermal || hotCyl ? 1.0 : (t.cht > 240 ? 0.65 : 0.0),
          glow: crownGlow,
          metallic: 0.9,
          roughness: 0.1,
          pick: true
        });

        // B. Volumetric 3D Thermal Heat Flux Projection Dome (Isothermal Envelope above Piston)
        if (thermal || hotCyl || (t.cht > 230 && isCombustionStroke)) {
          const domeAlpha = 0.14 + thermalIntensity * 0.24 + powerProgress * 0.25;
          const domeGlow = 0.75 + thermalIntensity * 0.35 + powerProgress * 0.45;
          add('sphere', 'pistons', Piston Thermal Projection Dome , [cx, pistonY + 0.54, 0], [0, 0, 0], [0.86, 0.42, 0.86], crownHeatColor, {
            alpha: clamp(domeAlpha, 0.08, 0.65),
            glow: clamp(domeGlow, 0.5, 1.2)
          });

          // C. Radial Isothermal Dissipation Rings (Heat Flux Transfer to Liner Wall)
          add('torus', 'pistons', Thermal Heat Flux Boundary , [cx, pistonY + 0.41, 0], [Math.PI / 2, 0, 0], [0.94, 0.94, 0.05], crownHeatColor, {
            alpha: 0.28 + thermalIntensity * 0.35,
            glow: 0.85 + powerProgress * 0.35
          });
        }

        // D. 3-Tier Thermal Ring Land Conduction Gradient (in Thermal Mode)
        if (thermal) {
          add('torus', 'pistons', Top Compression Ring Heat Land , [cx, pistonY + 0.32, 0], [Math.PI / 2, 0, 0], [0.84, 0.84, 0.05], ring1Color, { glow: 0.45 });
          add('torus', 'pistons', Scraper Ring Heat Land , [cx, pistonY + 0.24, 0], [Math.PI / 2, 0, 0], [0.84, 0.84, 0.05], ring2Color, { glow: 0.30 });
          add('torus', 'pistons', Oil Ring Heat Land , [cx, pistonY + 0.16, 0], [Math.PI / 2, 0, 0], [0.84, 0.84, 0.05], ring3Color, { glow: 0.18 });
        }

        // Combustion Flash inside combustion chamber during Power Stroke (0 <= cycle < PI)
        if (isCombustionStroke && t.rpm > 200) {
          const flashColor = misfire ? hexColor('#4a3c20') : hexColor('#ff9922');
          add('sphere', 'cylinders', Combustion Flame Flash , [cx, 1.82, 0], [0, 0, 0], [0.72 * powerProgress, 0.32 * powerProgress, 0.72 * powerProgress], flashColor, {
            alpha: 0.30 + powerProgress * 0.60,
            glow: 0.95 + powerProgress * 0.55
          });
        }
      });

      // -----------------------------------------------------------------------
      // 4. Cylinder Head & DOHC Valvetrain (Dual Camshafts, 8 Valves & Springs)
      // -----------------------------------------------------------------------
      const headY = 1.95 + explosion * 1.5;

      // Machined Cylinder Head Casting
      add('cube', 'cylinders', 'Cylinder Head Deck', [0, headY, 0], [0, 0, 0], [4.9, 0.48, 1.5], cylinderThermal, { alpha: housingAlpha, metallic: 0.45, pick: true });

      // Dual Camshafts (Intake at Z = +0.32, Exhaust at Z = -0.32)
      const camY = headY + 0.65;
      const camAngle = this.crankAngle * 0.5; // Camshaft rotates at half crank speed

      // Intake Camshaft
      add('cylinder', 'valvetrain', 'Intake Camshaft', [0, camY, 0.32], [0, 0, Math.PI / 2], [0.12, 0.12, 4.8], forgedSteel, { metallic: 0.85, pick: true });
      // Exhaust Camshaft
      add('cylinder', 'valvetrain', 'Exhaust Camshaft', [0, camY, -0.32], [0, 0, Math.PI / 2], [0.12, 0.12, 4.8], forgedSteel, { metallic: 0.85, pick: true });

      // Camshaft Timing Drive Sprockets (Front of engine)
      add('cylinder', 'valvetrain', 'Intake Cam Sprocket', [-2.45, camY, 0.32], [0, 0, Math.PI / 2], [0.46, 0.46, 0.08], forgedSteel, { metallic: 0.8 });
      add('cylinder', 'valvetrain', 'Exhaust Cam Sprocket', [-2.45, camY, -0.32], [0, 0, Math.PI / 2], [0.46, 0.46, 0.08], forgedSteel, { metallic: 0.8 });
      add('cylinder', 'valvetrain', 'Crank Timing Sprocket', [-2.45, 0, 0], [0, 0, Math.PI / 2], [0.28, 0.28, 0.08], forgedSteel, { metallic: 0.8 });

      // 8 Poppet Valves, Cam Lobes & Dynamic Compressing Helical Springs
      cylXs.forEach((cx, idx) => {
        const cycle = cycleAngles[idx];

        // Intake Valve Lift (during Intake stroke: 2*PI <= cycle < 3*PI)
        let intakeLift = 0;
        if (cycle >= Math.PI * 2 && cycle < Math.PI * 3) {
          intakeLift = Math.sin((cycle - Math.PI * 2) / Math.PI * Math.PI) * 0.15;
        }

        // Exhaust Valve Lift (during Exhaust stroke: PI <= cycle < 2*PI)
        let exhaustLift = 0;
        if (cycle >= Math.PI && cycle < Math.PI * 2) {
          exhaustLift = Math.sin((cycle - Math.PI) / Math.PI * Math.PI) * 0.15;
        }

        // Intake Cam Lobe
        add('camLobe', 'valvetrain', `Intake Cam Lobe ${idx + 1}`, [cx, camY, 0.32], [camAngle + idx * Math.PI * 0.5, 0, Math.PI / 2], [1, 1, 1], forgedSteel, { metallic: 0.9 });
        // Exhaust Cam Lobe
        add('camLobe', 'valvetrain', `Exhaust Cam Lobe ${idx + 1}`, [cx, camY, -0.32], [camAngle + idx * Math.PI * 0.5 + Math.PI * 0.5, 0, Math.PI / 2], [1, 1, 1], forgedSteel, { metallic: 0.9 });

        // Intake Valve (moves down into cylinder head when opened)
        add('valve', 'valvetrain', `Intake Valve ${idx + 1}`, [cx, headY + 0.38 - intakeLift, 0.32], [0, 0, 0], [1, 1, 1], brightAlum, { metallic: 0.9, pick: true });
        // Intake Valve Spring (compresses dynamically)
        const inSpringH = Math.max(0.24, 0.42 - intakeLift);
        add('spring', 'valvetrain', `Intake Spring ${idx + 1}`, [cx, headY + 0.30 - intakeLift * 0.5, 0.32], [0, 0, 0], [1, inSpringH / 0.42, 1], springSteel, { metallic: 0.85 });

        // Exhaust Valve (heat-treated alloy)
        const exValveColor = thermal ? exhaustThermal : hexColor('#9e8275');
        add('valve', 'valvetrain', `Exhaust Valve ${idx + 1}`, [cx, headY + 0.38 - exhaustLift, -0.32], [0, 0, 0], [1, 1, 1], exValveColor, { metallic: 0.85, glow: thermal ? 0.4 : 0, pick: true });
        // Exhaust Valve Spring
        const exSpringH = Math.max(0.24, 0.42 - exhaustLift);
        add('spring', 'valvetrain', `Exhaust Spring ${idx + 1}`, [cx, headY + 0.30 - exhaustLift * 0.5, -0.32], [0, 0, 0], [1, exSpringH / 0.42, 1], springSteel, { metallic: 0.85 });

        // Fuel Injector Bodies seated vertically in cylinder head
        add('cylinder', 'fuel', `Fuel Injector ${idx + 1}`, [cx, headY + 0.52, 0], [0, 0, 0], [0.12, 0.12, 0.45], fuelColor, { metallic: 0.8, glow: 0.25, pick: true });
      });

      // -----------------------------------------------------------------------
      // 5. Common Rail High-Pressure Fuel System
      // -----------------------------------------------------------------------
      const railY = headY + 0.78 + explosion * 0.4;
      add('cylinder', 'fuel', 'Common Rail Manifold', [0, railY, 0], [0, 0, Math.PI / 2], [0.14, 0.14, 4.4], fuelColor, { metallic: 0.9, glow: 0.35, pick: true });
      cylXs.forEach((cx, idx) => {
        add('cylinder', 'fuel', `High-Pressure Feed Line ${idx + 1}`, [cx, railY - 0.14, 0], [0, 0, 0], [0.04, 0.04, 0.28], fuelColor, { metallic: 0.8 });
      });

      // -----------------------------------------------------------------------
      // 6. Cast Aluminum Intake Plenum & Curved Runners
      // -----------------------------------------------------------------------
      const intakeZ = 0.95 + explosion * 1.4;
      add('cylinder', 'turbo', 'Intake Plenum Chamber', [0, headY + 0.20, intakeZ], [0, 0, Math.PI / 2], [0.38, 0.38, 4.6], intakeAlum, { alpha: 0.85, metallic: 0.7, pick: true });
      cylXs.forEach(cx => {
        add('cylinder', 'turbo', 'Intake Runner', [cx, headY + 0.10, intakeZ * 0.55], [Math.PI * 0.25, 0, 0], [0.18, 0.18, 0.65], intakeAlum, { metallic: 0.7 });
      });

      // -----------------------------------------------------------------------
      // 7. 4-into-1 Tuned Exhaust Header & Turbocharger
      // -----------------------------------------------------------------------
      const exhaustZ = -0.95 - explosion * 1.4;
      cylXs.forEach(cx => {
        add('cylinder', 'turbo', 'Exhaust Primary Pipe', [cx, headY - 0.10, exhaustZ * 0.55], [-Math.PI * 0.25, 0, 0], [0.18, 0.18, 0.65], exhaustThermal, { metallic: 0.6, glow: thermal ? 0.6 : 0 });
      });
      // Exhaust Collector Log
      add('cylinder', 'turbo', 'Exhaust Collector Log', [0.6, headY - 0.35, exhaustZ], [0, 0, Math.PI / 2], [0.34, 0.34, 3.2], exhaustThermal, { metallic: 0.6, glow: thermal ? 0.7 : 0 });

      // Turbocharger Assembly (Mounted at rear of engine X = 2.45)
      const turboPos = [2.45 + explosion * 1.5, headY - 0.25, -0.95];
      // Exhaust Turbine Volute Housing
      add('torus', 'turbo', 'Turbo Turbine Housing', turboPos, [0, Math.PI / 2, 0], [0.75, 0.75, 0.75], exhaustThermal, { metallic: 0.5, glow: thermal ? 0.8 : 0, pick: true });
      // Compressor Volute Housing
      add('torus', 'turbo', 'Turbo Compressor Housing', [turboPos[0] + 0.55, turboPos[1], turboPos[2]], [0, Math.PI / 2, 0], [0.82, 0.82, 0.82], castAlum, { metallic: 0.8, pick: true });
      // Spinning Compressor Wheel
      add('impeller', 'turbo', 'Turbo Compressor Impeller', [turboPos[0] + 0.55, turboPos[1], turboPos[2]], [0, 0, this.turboAngle], [1, 1, 1], polishedSteel, { metallic: 0.95 });
      // Center Bearing Housing & Wastegate Canister
      add('cylinder', 'turbo', 'Turbo Center Bearing Cartridge', [turboPos[0] + 0.28, turboPos[1], turboPos[2]], [0, 0, Math.PI / 2], [0.28, 0.28, 0.35], darkBlock, { metallic: 0.6 });
      add('cylinder', 'turbo', 'Wastegate Actuator', [turboPos[0] - 0.45, turboPos[1] + 0.35, turboPos[2]], [0, Math.PI * 0.25, Math.PI / 2], [0.18, 0.18, 0.45], forgedSteel, { metallic: 0.8 });

      // -----------------------------------------------------------------------
      // 8. Lubrication System: Cast Oil Sump, Pump, Filter & Galleries
      // -----------------------------------------------------------------------
      const sumpY = -1.15 - explosion * 1.2;
      // Deep Cast Aluminum Sump Pan
      add('cube', 'lubrication', 'Oil Sump Pan', [0, sumpY, 0], [0, 0, 0], [4.6, 0.52, 1.5], castAlum, { alpha: this.xray ? 0.35 : 1.0, metallic: 0.5, pick: true });
      // Sump Cooling Fins
      for (let fin = -1.8; fin <= 1.8; fin += 0.4) {
        add('cube', 'lubrication', 'Sump Cooling Fin', [fin, sumpY - 0.28, 0], [0, 0, 0], [0.04, 0.12, 1.4], darkBlock, { alpha: this.xray ? 0.3 : 1.0 });
      }
      // Spin-on Oil Filter Canister (Side mounted)
      add('cylinder', 'lubrication', 'Spin-On Oil Filter', [-1.8, sumpY + 0.25, 0.95], [Math.PI * 0.35, 0, 0], [0.38, 0.38, 0.65], oilColor, { metallic: 0.85, glow: 0.2, pick: true });
      // Main Oil Pressure Gallery Conduits
      add('cylinder', 'lubrication', 'Main Oil Gallery Line', [0, -0.32, 0.75], [0, 0, Math.PI / 2], [0.08, 0.08, 4.4], oilColor, { metallic: 0.8, glow: 0.3 });

      // Flowing Lubrication Particles (animated along oil gallery)
      const flowSpeed = Math.max(0.15, t.oilPressure / 50);
      for (let p = 0; p < 8; p += 1) {
        const px = (((time * 0.0008 * flowSpeed + p / 8) % 1) * 4.4) - 2.2;
        add('sphere', 'lubrication', 'Oil Flow Tracer', [px, -0.32, 0.75], [0, 0, 0], [0.09, 0.09, 0.09], oilColor, { glow: 0.85 });
      }

      // -----------------------------------------------------------------------
      // 9. Propeller Reduction Gearbox & Output Drive Flange
      // -----------------------------------------------------------------------
      const gbX = -2.85 - explosion * 1.5;
      // Gearbox Casing
      add('cylinder', 'propeller', 'Reduction Gearbox Casing', [gbX, 0.18, 0], [0, 0, Math.PI / 2], [0.95, 0.95, 0.72], castAlum, { metallic: 0.65, pick: true });
      // Propeller Drive Flange & Hub
      add('cylinder', 'propeller', 'Propeller Drive Flange', [gbX - 0.45, 0.18, 0], [0, 0, Math.PI / 2], [0.65, 0.65, 0.18], polishedSteel, { metallic: 0.95, pick: true });
      // Propeller Spinner Cone
      add('cylinder', 'propeller', 'Propeller Spinner Dome', [gbX - 0.85, 0.18, 0], [0, 0, Math.PI / 2], [0.15, 0.58, 0.65], polishedSteel, { metallic: 0.9 });
      // 3-Blade Propeller Blades
      const propAngle = this.crankAngle * 0.46;
      for (let b = 0; b < 3; b += 1) {
        const bAngle = propAngle + (b * Math.PI * 2) / 3;
        add('cube', 'propeller', `Propeller Blade ${b + 1}`, [gbX - 0.75, 0.18 + Math.cos(bAngle) * 1.8, Math.sin(bAngle) * 1.8], [bAngle, 0, 0], [0.12, 3.4, 0.24], hexColor('#2a382c'), { metallic: 0.3 });
      }

      // -----------------------------------------------------------------------
      // 10. Electrical Alternator & FADEC Dual-Channel ECU Enclosure
      // -----------------------------------------------------------------------
      const altPos = [1.6 + explosion * 1.2, -0.65 - explosion * 0.5, 0.95 + explosion * 0.6];
      add('cylinder', 'electrical', '28V Alternator Body', altPos, [0, 0, Math.PI / 2], [0.85, 0.85, 0.95], electricColor, { metallic: 0.8, glow: electricColor === red ? 0.9 : 0.15, pick: true });
      add('cylinder', 'electrical', 'Alternator Pulley', [altPos[0] - 0.55, altPos[1], altPos[2]], [0, 0, Math.PI / 2], [0.38, 0.38, 0.14], polishedSteel, { metallic: 0.9 });

      // FADEC Dual-Channel ECU Module (Firewall mounted)
      const fadecPos = [-0.6, headY + 0.95 + explosion * 0.8, -0.85];
      add('cube', 'electrical', 'FADEC Dual-Channel ECU', fadecPos, [0, 0, 0], [1.4, 0.42, 0.65], darkBlock, { metallic: 0.7, pick: true });
      add('cube', 'electrical', 'FADEC Military Connector J1', [fadecPos[0] - 0.4, fadecPos[1], fadecPos[2] - 0.36], [0, 0, 0], [0.22, 0.18, 0.14], bronze, { metallic: 0.9 });
      add('cube', 'electrical', 'FADEC Military Connector J2', [fadecPos[0] + 0.4, fadecPos[1], fadecPos[2] - 0.36], [0, 0, 0], [0.22, 0.18, 0.14], bronze, { metallic: 0.9 });

      // -----------------------------------------------------------------------
      // 11. Redundant FADEC Sensor Nodes (CHT, EGT, MAP, Oil, Crank)
      // -----------------------------------------------------------------------
      const sensorNodes = [
        { name: 'CHT Sensor Probe', pos: [-0.60, headY + 0.25, 0.65] },
        { name: 'EGT Thermocouple Probe', pos: [0.60, headY - 0.25, -0.95] },
        { name: 'Oil Pressure Transducer', pos: [-1.80, sumpY + 0.55, 0.75] },
        { name: 'Manifold Pressure (MAP)', pos: [0.60, headY + 0.35, 0.95] },
        { name: 'Crank Position Sensor', pos: [-2.40, 0.38, 0.0] }
      ];

      sensorNodes.forEach((sn, sIdx) => {
        const sensorFault = fault.includes('sensor') && sIdx === 0;
        const pulse = 0.12 + Math.sin(time * 0.006 + sIdx) * 0.03;
        const sColor = sensorFault ? red : green;
        add('sphere', 'sensors', sn.name, [sn.pos[0], sn.pos[1], sn.pos[2]], [0, 0, 0], [pulse, pulse, pulse], sColor, {
          glow: sensorFault ? 1.0 : 0.65,
          pick: true
        });
      });

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
      parts.filter(p => p.pick).forEach(part => {
        if (seen.has(part.component)) return;
        seen.add(part.component);
        const pt = transformPoint(viewProjection, part.position);
        if (pt[2] < -1 || pt[2] > 1) return;
        this.pickTargets.push({
          component: part.component,
          x: (pt[0] * 0.5 + 0.5) * rect.width,
          y: (1 - (pt[1] * 0.5 + 0.5)) * rect.height,
          radius: 38
        });
      });
    }

    drawGrid() {
      const gridColor = hexColor('#152417');
      for (let i = -7; i <= 7; i += 1) {
        this.drawPart(this.part('cube', 'grid', 'Grid', [i * 0.85, -2.4, 0], [0, 0, 0], [0.015, 0.015, 12], gridColor, { alpha: 0.32 }));
        this.drawPart(this.part('cube', 'grid', 'Grid', [0, -2.4, i * 0.85], [0, 0, 0], [12, 0.015, 0.015], gridColor, { alpha: 0.32 }));
      }
    }

    frame(time) {
      const delta = Math.min(0.05, (time - this.lastTime) / 1000);
      this.lastTime = time;
      this.resize();

      // Kinematic Crankshaft Angular Velocity Drive
      if (!this.paused && !this.reducedMotion) {
        const rawRpm = Number(this.telemetry.rpm) || 0;
        const state = String(this.telemetry.engineState || '').toUpperCase();
        const isRunning = rawRpm > 0 && state !== 'ENGINE_OFF' && state !== 'OFF';
        if (isRunning) {
          const revsPerSec = clamp(rawRpm / 60, 0, 110);
          // 4-Stroke cycle spans 4*PI (720 degrees)
          this.crankAngle = (this.crankAngle + delta * revsPerSec * Math.PI * 2 * 0.40) % (Math.PI * 4);
          this.turboAngle = (this.turboAngle + delta * revsPerSec * Math.PI * 2 * 1.8) % (Math.PI * 2);
        }
      }

      // Smooth Explode Animation Transition
      this.explodeAmount += ((this.exploded ? 1.0 : 0.0) - this.explodeAmount) * Math.min(1.0, delta * 5.5);

      const gl = this.gl;
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);

      const rect = this.canvas.getBoundingClientRect();
      const aspect = Math.max(0.2, rect.width / Math.max(1, rect.height));
      const projection = mat4Perspective(36 * DEG, aspect, 0.1, 100);

      const cam = this.camera;
      const horiz = Math.cos(cam.pitch) * cam.distance;
      const eye = [
        Math.sin(cam.yaw) * horiz,
        Math.sin(cam.pitch) * cam.distance + 0.35,
        Math.cos(cam.yaw) * horiz
      ];
      const view = mat4LookAt(eye, [0, 0.35, 0], [0, 1, 0]);

      gl.useProgram(this.program);
      gl.uniformMatrix4fv(this.locations.view, false, view);
      gl.uniformMatrix4fv(this.locations.projection, false, projection);

      this.drawGrid();

      // Vibration & Jitter Modes
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

      // Render Opaque Geometry first with full Depth Mask, followed by Translucent Parts
      const opaque = parts.filter(p => p.alpha >= 0.95);
      const translucent = parts.filter(p => p.alpha < 0.95);

      gl.depthMask(true);
      opaque.forEach(p => this.drawPart(p));

      gl.depthMask(false);
      translucent.forEach(p => this.drawPart(p));
      gl.depthMask(true);

      this.buildPickTargets(parts, mat4Multiply(projection, view));
      requestAnimationFrame(next => this.frame(next));
    }
  }

  function showFallback(error) {
    const shell = document.querySelector('.engine-viewport');
    if (!shell) return;
    shell.innerHTML = `<div class="engine-fallback"><strong>3D engine fallback active</strong><span>${error.message}</span><span>Telemetry and AI analysis remain available.</span></div>`;
  }

  function init() {
    const canvas = document.getElementById('engineCanvas');
    if (!canvas) return;
    try {
      const renderer = new AeroEngineRenderer(canvas);
      window.AeroPulseEngine3D = {
        setTelemetry: data => renderer.setTelemetry(data || {}),
        setMode: mode => renderer.setMode(mode),
        resetCamera: () => renderer.resetCamera(),
        renderer
      };
      renderer.updateHud();
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
