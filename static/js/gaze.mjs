export const EYE_LANDMARK_INDICES = {
  eyeA: [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246],
  eyeB: [362, 398, 384, 385, 386, 387, 388, 466, 263, 249, 390, 373, 374, 380, 381, 382],
};

export const IRIS_LANDMARK_INDICES = {
  eyeA: [468, 469, 470, 471, 472],
  eyeB: [473, 474, 475, 476, 477],
};

export const CALIBRATION_TARGETS = [
  { x: 0.12, y: 0.12 },
  { x: 0.88, y: 0.12 },
  { x: 0.5, y: 0.5 },
  { x: 0.12, y: 0.88 },
  { x: 0.88, y: 0.88 },
];

export const CALIBRATION_SAMPLES_PER_TARGET = 8;

function isValidPoint(point) {
  return (
    point &&
    Number.isFinite(point.x) &&
    Number.isFinite(point.y) &&
    point.x >= 0 &&
    point.x <= 1 &&
    point.y >= 0 &&
    point.y <= 1
  );
}

function estimateEye(landmarks, boundaryIndices, irisIndices) {
  const boundary = boundaryIndices.map((index) => landmarks[index]);
  const iris = irisIndices.map((index) => landmarks[index]);
  if (!boundary.every(isValidPoint) || !iris.every(isValidPoint)) return null;

  const xs = boundary.map((point) => point.x);
  const ys = boundary.map((point) => point.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const width = maxX - minX;
  const height = maxY - minY;
  if (width < 0.012 || height < 0.004) return null;

  const irisX = iris.reduce((sum, point) => sum + point.x, 0) / iris.length;
  const irisY = iris.reduce((sum, point) => sum + point.y, 0) / iris.length;
  const horizontal = (irisX - minX) / width;
  const vertical = (irisY - minY) / height;
  if (horizontal < 0 || horizontal > 1 || vertical < 0 || vertical > 1) return null;

  return { x: horizontal, y: vertical };
}

export function estimateGaze(landmarks) {
  const requiredLength = Math.max(
    ...EYE_LANDMARK_INDICES.eyeA,
    ...EYE_LANDMARK_INDICES.eyeB,
    ...IRIS_LANDMARK_INDICES.eyeA,
    ...IRIS_LANDMARK_INDICES.eyeB,
  ) + 1;
  if (!Array.isArray(landmarks) || landmarks.length < requiredLength) {
    return { valid: false, direction: "unavailable", reason: "missing-landmarks" };
  }

  const eyeA = estimateEye(landmarks, EYE_LANDMARK_INDICES.eyeA, IRIS_LANDMARK_INDICES.eyeA);
  const eyeB = estimateEye(landmarks, EYE_LANDMARK_INDICES.eyeB, IRIS_LANDMARK_INDICES.eyeB);
  if (!eyeA || !eyeB) {
    return { valid: false, direction: "unavailable", reason: "unreliable-eyes" };
  }
  if (Math.abs(eyeA.x - eyeB.x) > 0.55 || Math.abs(eyeA.y - eyeB.y) > 0.55) {
    return { valid: false, direction: "unavailable", reason: "inconsistent-eyes" };
  }

  const x = 1 - (eyeA.x + eyeB.x) / 2;
  const y = (eyeA.y + eyeB.y) / 2;
  const horizontalOffset = x - 0.5;
  const verticalOffset = y - 0.5;
  let direction = "center";
  if (Math.abs(horizontalOffset) >= Math.abs(verticalOffset)) {
    if (horizontalOffset < -0.14) direction = "left";
    else if (horizontalOffset > 0.14) direction = "right";
  } else if (verticalOffset < -0.14) {
    direction = "up";
  } else if (verticalOffset > 0.14) {
    direction = "down";
  }
  return { valid: true, x, y, direction };
}

export function createCalibration() {
  return {
    targets: CALIBRATION_TARGETS.map((target) => ({ ...target, samples: [] })),
    currentTarget: 0,
    coefficients: null,
    complete: false,
  };
}

export function addCalibrationSample(calibration, gaze) {
  if (
    !calibration ||
    calibration.complete ||
    !gaze?.valid ||
    !Number.isFinite(gaze.x) ||
    !Number.isFinite(gaze.y) ||
    gaze.x < 0 ||
    gaze.x > 1 ||
    gaze.y < 0 ||
    gaze.y > 1
  ) {
    return { accepted: false, complete: Boolean(calibration?.complete) };
  }

  const target = calibration.targets[calibration.currentTarget];
  if (!target) return { accepted: false, complete: false };
  target.samples.push({ x: gaze.x, y: gaze.y });

  if (target.samples.length >= CALIBRATION_SAMPLES_PER_TARGET) {
    calibration.currentTarget += 1;
    if (calibration.currentTarget >= calibration.targets.length) {
      calibration.coefficients = fitCalibration(calibration.targets);
      calibration.complete = Boolean(calibration.coefficients);
    }
  }
  return {
    accepted: true,
    complete: calibration.complete,
    failed: calibration.currentTarget >= calibration.targets.length && !calibration.complete,
    targetIndex: calibration.currentTarget,
    sampleCount: target.samples.length,
  };
}

function solve3x3(matrix, values) {
  const augmented = matrix.map((row, index) => [...row, values[index]]);
  for (let column = 0; column < 3; column += 1) {
    let pivot = column;
    for (let row = column + 1; row < 3; row += 1) {
      if (Math.abs(augmented[row][column]) > Math.abs(augmented[pivot][column])) {
        pivot = row;
      }
    }
    if (Math.abs(augmented[pivot][column]) < 1e-10) return null;
    [augmented[column], augmented[pivot]] = [augmented[pivot], augmented[column]];
    const divisor = augmented[column][column];
    for (let index = column; index < 4; index += 1) {
      augmented[column][index] /= divisor;
    }
    for (let row = 0; row < 3; row += 1) {
      if (row === column) continue;
      const factor = augmented[row][column];
      for (let index = column; index < 4; index += 1) {
        augmented[row][index] -= factor * augmented[column][index];
      }
    }
  }
  return augmented.map((row) => row[3]);
}

function fitCalibration(targets) {
  const samples = targets.flatMap((target) =>
    target.samples.map((sample) => ({ ...sample, targetX: target.x, targetY: target.y })),
  );
  if (
    targets.length !== CALIBRATION_TARGETS.length ||
    targets.some((target) => target.samples.length < CALIBRATION_SAMPLES_PER_TARGET)
  ) {
    return null;
  }

  const normal = [
    [0, 0, 0],
    [0, 0, 0],
    [0, 0, 0],
  ];
  const xValues = [0, 0, 0];
  const yValues = [0, 0, 0];
  samples.forEach((sample) => {
    const row = [sample.x, sample.y, 1];
    for (let i = 0; i < 3; i += 1) {
      xValues[i] += row[i] * sample.targetX;
      yValues[i] += row[i] * sample.targetY;
      for (let j = 0; j < 3; j += 1) {
        normal[i][j] += row[i] * row[j];
      }
    }
  });
  const xCoefficients = solve3x3(normal, xValues);
  const yCoefficients = solve3x3(normal, yValues);
  return xCoefficients && yCoefficients
    ? { x: xCoefficients, y: yCoefficients }
    : null;
}

export function applyCalibration(calibration, gaze) {
  if (!calibration?.complete || !calibration.coefficients || !gaze?.valid) return null;
  const [x0, x1, xOffset] = calibration.coefficients.x;
  const [y0, y1, yOffset] = calibration.coefficients.y;
  const x = x0 * gaze.x + x1 * gaze.y + xOffset;
  const y = y0 * gaze.x + y1 * gaze.y + yOffset;
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  return {
    x: Math.min(1, Math.max(0, x)),
    y: Math.min(1, Math.max(0, y)),
  };
}
