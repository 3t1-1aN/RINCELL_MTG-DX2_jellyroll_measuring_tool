/**
 * Polar SVG visualizer for jellyroll radius samples.
 *
 * Plots every captured radius point (e.g. 12), not stitched diameters.
 * Concentric rings are 0.1 mm radius steps; the target radius ring is bold.
 * The two radii that form the max stitched diameter are green; the two that
 * form the min stitched diameter are red.
 */
(function (global) {
    "use strict";

    const DEG = Math.PI / 180;
    const RING_STEP_MM = 0.1;

    function sampleAngle(sample, total) {
        if (sample.angle != null && !Number.isNaN(Number(sample.angle))) {
            return Number(sample.angle);
        }
        const idx = sample.index != null ? sample.index : 1;
        return (idx - 1) * (360 / Math.max(total, 1));
    }

    function radiusSamples(result) {
        if (result.radius_samples && result.radius_samples.length) {
            return result.radius_samples;
        }
        return [];
    }

    function polarToXY(cx, cy, radiusPx, angleDeg) {
        const rad = angleDeg * DEG;
        return {
            x: cx + radiusPx * Math.sin(rad),
            y: cy - radiusPx * Math.cos(rad),
        };
    }

    function radialOffset(cx, cy, point, distance) {
        const dx = point.x - cx;
        const dy = point.y - cy;
        const len = Math.hypot(dx, dy) || 1;
        return {
            x: point.x + (dx / len) * distance,
            y: point.y + (dy / len) * distance,
        };
    }

    function fmt(value, digits) {
        return Number(value).toFixed(digits);
    }

    function floorToStep(value, step) {
        return Math.floor(value / step + 1e-9) * step;
    }

    function ceilToStep(value, step) {
        return Math.ceil(value / step - 1e-9) * step;
    }

    /**
     * Opposite-radius stitching: diameter i pairs radius i with radius i + n/2.
     * Returns { minRadiusIndexes, maxRadiusIndexes, minDiameter, maxDiameter }.
     */
    function minMaxDiameterRadiusIndexes(samples, result) {
        const byIndex = new Map();
        for (const sample of samples) {
            byIndex.set(Number(sample.index), Number(sample.value));
        }
        const indexes = [...byIndex.keys()].sort((a, b) => a - b);
        const total = indexes.length;
        const pairCount = Math.floor(total / 2);
        if (pairCount < 1) {
            return {
                minRadiusIndexes: new Set(),
                maxRadiusIndexes: new Set(),
                minDiameter: null,
                maxDiameter: null,
            };
        }

        const diameters = [];
        for (let i = 0; i < pairCount; i++) {
            const firstIndex = indexes[i];
            const oppositeIndex = indexes[i + pairCount];
            const value = byIndex.get(firstIndex) + byIndex.get(oppositeIndex);
            diameters.push({
                diameterIndex: i + 1,
                value,
                radiusIndexes: [firstIndex, oppositeIndex],
            });
        }

        let minDia = diameters[0];
        let maxDia = diameters[0];
        const preferMin = result.min_sample_index != null ? Number(result.min_sample_index) : null;
        const preferMax = result.max_sample_index != null ? Number(result.max_sample_index) : null;

        if (preferMin != null) {
            const match = diameters.find((dia) => dia.diameterIndex === preferMin);
            if (match) minDia = match;
        } else {
            for (const dia of diameters) {
                if (dia.value < minDia.value) minDia = dia;
            }
        }

        if (preferMax != null) {
            const match = diameters.find((dia) => dia.diameterIndex === preferMax);
            if (match) maxDia = match;
        } else {
            for (const dia of diameters) {
                if (dia.value > maxDia.value) maxDia = dia;
            }
        }

        return {
            minRadiusIndexes: new Set(minDia.radiusIndexes),
            maxRadiusIndexes: new Set(maxDia.radiusIndexes),
            minDiameter: minDia.value,
            maxDiameter: maxDia.value,
        };
    }

    function pointRole(sampleIndex, minRadiusIndexes, maxRadiusIndexes) {
        if (maxRadiusIndexes.has(sampleIndex)) return "max";
        if (minRadiusIndexes.has(sampleIndex)) return "min";
        return "ok";
    }

    function renderDiameterViz(container, result, options) {
        if (!container || !result) return;

        const opts = options || {};
        const size = opts.size || 560;
        const pad = opts.pad ?? Math.round(size * 0.14);
        const digits = opts.digits ?? 3;
        const showLegend = opts.showLegend !== false;
        const title = opts.title || "";
        const ringStep = Number(opts.ringStepMm ?? RING_STEP_MM);

        const targetDiameter = Number(result.target ?? opts.target ?? result.nominal ?? opts.nominal ?? 0);
        const tolerance = Number(result.tolerance ?? opts.tolerance ?? 0);
        const targetRadius = targetDiameter / 2;
        const radiusTol = tolerance / 2;

        const samples = radiusSamples(result);
        const total = samples.length || Number(result.radius_sample_count) || Number(opts.totalSamples) || 0;

        if (!samples.length) {
            container.innerHTML =
                '<div class="diameter-viz-empty">No radius sample data — capture radius points to plot the profile.</div>';
            return;
        }

        const values = samples.map((s) => Number(s.value));
        const minVal = Math.min(...values);
        const maxVal = Math.max(...values);
        const tirMm = Number(result.tir ?? (maxVal - minVal) * 2);
        const { minRadiusIndexes, maxRadiusIndexes, minDiameter, maxDiameter } = minMaxDiameterRadiusIndexes(
            samples,
            result
        );

        // Zoomed annular scale (center is not 0), like the reference plots.
        const rangeMin = Math.min(minVal, targetRadius - radiusTol);
        const rangeMax = Math.max(maxVal, targetRadius + radiusTol);
        let origin = floorToStep(rangeMin - ringStep * 0.5, ringStep);
        let outer = ceilToStep(rangeMax + ringStep * 0.5, ringStep);
        if (outer - origin < ringStep * 4) {
            origin = floorToStep(targetRadius - ringStep * 2, ringStep);
            outer = ceilToStep(targetRadius + ringStep * 2, ringStep);
        }
        origin = Math.max(0, origin);
        const span = Math.max(outer - origin, ringStep);

        const cx = size / 2;
        const cy = size / 2;
        const maxRadiusPx = (size - pad * 2) / 2;
        const labelSize = Math.round(size * 0.028);
        const angleLabelSize = Math.round(size * 0.026);
        const markerLabelSize = Math.round(size * 0.032);
        const dotSize = Math.max(4, Math.round(size * 0.012));
        const markerDotSize = Math.max(6, Math.round(size * 0.016));
        const labelOffset = Math.round(size * 0.055);
        const labelMargin = Math.round(size * 0.03);

        function radiusPxForMeasurement(valueMm) {
            const t = (Number(valueMm) - origin) / span;
            return Math.max(0, Math.min(maxRadiusPx, t * maxRadiusPx));
        }

        const targetR = radiusPxForMeasurement(targetRadius);
        const tolOuterR = radiusPxForMeasurement(targetRadius + radiusTol);
        const tolInnerR = radiusPxForMeasurement(Math.max(targetRadius - radiusTol, origin));

        const ringValues = [];
        for (let v = origin + ringStep; v <= outer + 1e-9; v += ringStep) {
            ringValues.push(Math.round(v / ringStep) * ringStep);
        }

        const plotted = samples
            .map((sample) => {
                const angle = sampleAngle(sample, total);
                const value = Number(sample.value);
                const radiusPx = radiusPxForMeasurement(value);
                const point = polarToXY(cx, cy, radiusPx, angle);
                const role = pointRole(Number(sample.index), minRadiusIndexes, maxRadiusIndexes);
                return { sample, angle, value, radiusPx, point, role };
            })
            .sort((a, b) => a.angle - b.angle);

        const outline = plotted.map((p) => `${p.point.x.toFixed(2)},${p.point.y.toFixed(2)}`).join(" ");

        const spokeAngles = [];
        const angleStep = 360 / Math.max(total, 1);
        for (let i = 0; i < Math.max(total, 1); i++) {
            spokeAngles.push(i * angleStep);
        }

        const spokes = spokeAngles
            .map((angle) => {
                const tip = polarToXY(cx, cy, maxRadiusPx, angle);
                return `<line class="diameter-viz-spoke" x1="${cx}" y1="${cy}" x2="${tip.x.toFixed(2)}" y2="${tip.y.toFixed(2)}" />`;
            })
            .join("\n");

        const angleLabels = spokeAngles
            .map((angle) => {
                const tip = polarToXY(cx, cy, maxRadiusPx + labelSize * 1.6, angle);
                return `<text class="diameter-viz-angle" x="${tip.x.toFixed(1)}" y="${tip.y.toFixed(1)}" text-anchor="middle" dominant-baseline="middle" font-size="${angleLabelSize}px">${fmt(angle, 0)}°</text>`;
            })
            .join("\n");

        const rings = ringValues
            .map((valueMm) => {
                const r = radiusPxForMeasurement(valueMm);
                if (r <= 0) return "";
                return `<circle class="diameter-viz-ring" cx="${cx}" cy="${cy}" r="${r.toFixed(2)}" />`;
            })
            .join("\n");

        const labelAngle = spokeAngles.find((a) => a > 0) ?? 30;
        const ringLabels = ringValues
            .map((valueMm) => {
                const r = radiusPxForMeasurement(valueMm);
                if (r <= 0) return "";
                const pt = polarToXY(cx, cy, r, labelAngle);
                const isNearTarget = Math.abs(valueMm - targetRadius) < ringStep * 0.5;
                const cls = isNearTarget ? "diameter-viz-ring-label target" : "diameter-viz-ring-label";
                return `<text class="${cls}" x="${(pt.x + 4).toFixed(1)}" y="${pt.y.toFixed(1)}" font-size="${labelSize}px">${fmt(valueMm, 1)}</text>`;
            })
            .join("\n");

        const outlineDots = plotted
            .map((p) => {
                const r = p.role === "ok" ? dotSize : markerDotSize;
                const roleNote =
                    p.role === "max"
                        ? `max Ø pair (${fmt(maxDiameter, digits)} mm)`
                        : p.role === "min"
                          ? `min Ø pair (${fmt(minDiameter, digits)} mm)`
                          : "other";
                const titleText = `R${p.sample.index}: ${fmt(p.value, digits)} mm @ ${fmt(p.angle, 0)}° — ${roleNote}`;
                return `<title>${titleText}</title><circle class="diameter-viz-point ${p.role}" cx="${p.point.x.toFixed(2)}" cy="${p.point.y.toFixed(2)}" r="${r}" />`;
            })
            .join("\n");

        function pairLabel(role, diameterMm) {
            const members = plotted.filter((p) => p.role === role);
            if (!members.length || diameterMm == null) return "";
            const anchor = members[0];
            const raw = radialOffset(cx, cy, anchor.point, labelOffset);
            const x = Math.max(labelMargin, Math.min(size - labelMargin, raw.x));
            const y = Math.max(labelMargin + markerLabelSize, Math.min(size - labelMargin, raw.y));
            const textAnchor = x >= cx ? "start" : "end";
            return `
                <text class="diameter-viz-minmax ${role}" x="${x.toFixed(1)}" y="${y.toFixed(1)}" text-anchor="${textAnchor}" font-size="${markerLabelSize}px">
                    ${role === "min" ? "MIN" : "MAX"} Ø ${fmt(diameterMm, digits)}
                </text>
            `;
        }

        const passClass = result.pass ? "pass" : "fail";
        const originLabel = fmt(origin, 1);
        const defaultTitle = `Radius profile (radial origin = ${originLabel} mm)`;

        container.innerHTML = `
            <div class="diameter-viz ${passClass}">
                <div class="diameter-viz-title">${title || defaultTitle}</div>
                <svg class="diameter-viz-svg" viewBox="0 0 ${size} ${size}" width="${size}" height="${size}" role="img" aria-label="Radius profile visualizer">
                    <rect class="diameter-viz-bg" x="0" y="0" width="${size}" height="${size}" rx="12" />
                    ${spokes}
                    ${rings}
                    <circle class="diameter-viz-tol-limit" cx="${cx}" cy="${cy}" r="${tolOuterR.toFixed(2)}" />
                    <circle class="diameter-viz-tol-limit" cx="${cx}" cy="${cy}" r="${tolInnerR.toFixed(2)}" />
                    <circle class="diameter-viz-ring target" cx="${cx}" cy="${cy}" r="${targetR.toFixed(2)}" />
                    <polygon class="diameter-viz-outline" points="${outline}" />
                    ${outlineDots}
                    ${pairLabel("min", minDiameter)}
                    ${pairLabel("max", maxDiameter)}
                    ${ringLabels}
                    ${angleLabels}
                    <circle class="diameter-viz-center" cx="${cx}" cy="${cy}" r="2.5" />
                </svg>
                ${
                    showLegend
                        ? `<div class="diameter-viz-legend">
                            <span><i class="swatch target"></i>Target R ${fmt(targetRadius, digits)} mm</span>
                            <span><i class="swatch tol"></i>±${fmt(radiusTol, digits)} mm (R)</span>
                            <span><i class="swatch max"></i>Max Ø radii</span>
                            <span><i class="swatch min"></i>Min Ø radii</span>
                            <span><i class="swatch tir"></i>TIR ${fmt(tirMm, digits)} mm</span>
                            <span>Rings ${fmt(ringStep, 1)} mm</span>
                        </div>`
                        : ""
                }
            </div>
        `;
    }

    global.renderDiameterViz = renderDiameterViz;
})(typeof window !== "undefined" ? window : globalThis);
