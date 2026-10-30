import assert from "node:assert/strict";
import test from "node:test";

import {
  addCalibrationSample,
  applyCalibration,
  CALIBRATION_SAMPLES_PER_TARGET,
  CALIBRATION_TARGETS,
  createCalibration,
  EYE_LANDMARK_INDICES,
  estimateGaze,
  IRIS_LANDMARK_INDICES,
} from "../static/js/gaze.mjs";

function makeLandmarks(gazeX = 0.5, gazeY = 0.5) {
  const landmarks = Array.from({ length: 478 }, () => ({ x: 0.5, y: 0.5 }));
  const makeEye = (boundaryIndices, irisIndices, minX) => {
    const minY = 0.4;
    const width = 0.1;
    const height = 0.08;
    const outline = [
      { x: minX, y: minY + height / 2 },
      { x: minX + width / 2, y: minY },
      { x: minX + width, y: minY + height / 2 },
      { x: minX + width / 2, y: minY + height },
    ];
    boundaryIndices.forEach((index, pointIndex) => {
      landmarks[index] = outline[pointIndex % outline.length];
    });
    const irisPoint = {
      x: minX + (1 - gazeX) * width,
      y: minY + gazeY * height,
    };
    irisIndices.forEach((index) => {
      landmarks[index] = irisPoint;
    });
  };
  makeEye(EYE_LANDMARK_INDICES.eyeA, IRIS_LANDMARK_INDICES.eyeA, 0.2);
  makeEye(EYE_LANDMARK_INDICES.eyeB, IRIS_LANDMARK_INDICES.eyeB, 0.65);
  return landmarks;
}

test("estimateGaze returns approximate center and cardinal directions", () => {
  assert.equal(estimateGaze(makeLandmarks()).direction, "center");
  assert.equal(estimateGaze(makeLandmarks(0.1, 0.5)).direction, "left");
  assert.equal(estimateGaze(makeLandmarks(0.9, 0.5)).direction, "right");
  assert.equal(estimateGaze(makeLandmarks(0.5, 0.1)).direction, "up");
  assert.equal(estimateGaze(makeLandmarks(0.5, 0.9)).direction, "down");
});

test("estimateGaze rejects missing, collapsed, and out-of-eye landmarks", () => {
  assert.equal(estimateGaze([]).valid, false);

  const collapsed = makeLandmarks();
  EYE_LANDMARK_INDICES.eyeA.forEach((index) => {
    collapsed[index] = { x: 0.25, y: 0.44 };
  });
  assert.equal(estimateGaze(collapsed).reason, "unreliable-eyes");

  const outsideEye = makeLandmarks();
  IRIS_LANDMARK_INDICES.eyeA.forEach((index) => {
    outsideEye[index] = { x: 0.1, y: 0.44 };
  });
  assert.equal(estimateGaze(outsideEye).valid, false);
});

test("calibration ignores invalid samples and solves a five-point mapping", () => {
  const calibration = createCalibration();
  assert.equal(addCalibrationSample(calibration, { valid: false }).accepted, false);
  assert.equal(addCalibrationSample(calibration, { valid: true, x: 2, y: 0.5 }).accepted, false);

  let result;
  for (const target of CALIBRATION_TARGETS) {
    for (let sample = 0; sample < CALIBRATION_SAMPLES_PER_TARGET; sample += 1) {
      result = addCalibrationSample(calibration, {
        valid: true,
        x: target.x,
        y: target.y,
      });
    }
  }

  assert.equal(result.complete, true);
  for (const target of CALIBRATION_TARGETS) {
    const point = applyCalibration(calibration, {
      valid: true,
      x: target.x,
      y: target.y,
    });
    assert.ok(Math.abs(point.x - target.x) < 1e-8);
    assert.ok(Math.abs(point.y - target.y) < 1e-8);
  }
});

test("calibration refuses a degenerate point mapping", () => {
  const calibration = createCalibration();
  let result;
  for (let sample = 0; sample < CALIBRATION_TARGETS.length * CALIBRATION_SAMPLES_PER_TARGET; sample += 1) {
    result = addCalibrationSample(calibration, { valid: true, x: 0.5, y: 0.5 });
  }
  assert.equal(result.complete, false);
  assert.equal(result.failed, true);
  assert.equal(applyCalibration(calibration, { valid: true, x: 0.5, y: 0.5 }), null);
});
