/**
 * Polar SVG visualizer for jellyroll diameter samples.
 *
 * True geometric scaling hides ±0.2–0.5 mm on a ~17 mm roll, so deviations from
 * nominal are amplified while keeping the outline round and readable.
 */
(function (global) {
    "use strict";

    const DEG = Math.PI / 180;
    // Typical jellyroll surface variation window used when measured TIR is tiny.
    const MIN_DEVIATION_WINDOW_MM = 0.25;

    function sampleAngle(sample, total) {
        if (sample.angle != null && !Number.isNaN(Number(sample.angle))) {
            return Number(sample.angle);
        }
        const idx = sample.index != null ? sample.index : 1;
        return (idx - 1) * (360 / Math.max(total, 1));
    }

    function normalizeSamples(result) {
        if (result.samples && result.samples.length) {
            return result.samples;
        }
        const points = result.points || [];
        return points.map((value, i) => ({
            index: i + 1,
            value,
            angle: null,
            ok: true,
        }));
    }

    function outlineSamples(result) {
        if (result.radius_samples && result.radius_samples.length) {
            return {
                samples: result.radius_samples,
                mode: "radius",
            };
        }
        return {
            samples: normalizeSamples(result),
            mode: "diameter",
        };
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

    function renderDiameterViz(container, result, options) {
        if (!container || !result) return;

        const opts = options || {};
        const size = opts.size || 560;
        // Extra pad so MIN/MAX labels on the left/right stay inside the box.
        const pad = opts.pad ?? Math.round(size * 0.18);
        const digits = opts.digits ?? 3;
        const labelSize = Math.round(size * 0.036);
        const subLabelSize = Math.round(size * 0.028);
        const labelOffset = Math.round(size * 0.055);
        const labelMargin = Math.round(size * 0.03);
        const dotSize = Math.max(4, Math.round(size * 0.012));
        const markerDotSize = Math.max(6, Math.round(size * 0.016));
        const showLegend = opts.showLegend !== false;
        const title = opts.title || "";

        const nominalDiameter = Number(result.nominal ?? opts.nominal ?? 0);
        const tolerance = Number(result.tolerance ?? opts.tolerance ?? 0);
        const outlineData = outlineSamples(result);
        const outlineMode = outlineData.mode;
        const outlinePoints = outlineData.samples;
        const diameterSamples = normalizeSamples(result);
        const total = outlinePoints.length || diameterSamples.length || Number(opts.totalSamples) || 1;

        if (!outlinePoints.length && !diameterSamples.length) {
            container.innerHTML = '<div class="diameter-viz-empty">No sample data</div>';
            return;
        }

        const diameterValues = diameterSamples.map((s) => Number(s.value));
        const minVal = Number(result.min ?? (diameterValues.length ? Math.min(...diameterValues) : 0));
        const maxVal = Number(result.max ?? (diameterValues.length ? Math.max(...diameterValues) : 0));
        const minIndex = result.min_sample_index;
        const maxIndex = result.max_sample_index;
        const tirMm = Number(result.tir ?? maxVal - minVal);

        const nominal = outlineMode === "radius" ? nominalDiameter / 2 : nominalDiameter;
        const toleranceBand = outlineMode === "radius" ? tolerance / 2 : tolerance;

        const cx = size / 2;
        const cy = size / 2;
        const maxRadiusPx = (size - pad * 2) / 2;

        // Amplify small diameter deviations so ±0.2–0.5 mm is visible on the outline.
        // Nominal sits at ~70% of the drawable radius; the remaining band is for deviation.
        const baseRadiusPx = maxRadiusPx * 0.7;
        const ampBandPx = maxRadiusPx * 0.28;
        const outlineValues = outlinePoints.map((s) => Number(s.value));
        const peakAbsDevMm = Math.max(
            ...outlineValues.map((value) => Math.abs(value - nominal)),
            Math.abs(maxVal / (outlineMode === "radius" ? 2 : 1) - nominal),
            Math.abs(minVal / (outlineMode === "radius" ? 2 : 1) - nominal),
            tirMm / 2,
            toleranceBand,
            MIN_DEVIATION_WINDOW_MM
        );
        const pxPerMm = ampBandPx / peakAbsDevMm;

        function radiusPxForMeasurement(valueMm) {
            const amplified = baseRadiusPx + (Number(valueMm) - nominal) * pxPerMm;
            return Math.max(maxRadiusPx * 0.18, Math.min(maxRadiusPx, amplified));
        }

        const nominalR = radiusPxForMeasurement(nominal);
        const tolOuterR = radiusPxForMeasurement(nominal + toleranceBand);
        const tolInnerR = radiusPxForMeasurement(Math.max(nominal - toleranceBand, 0));
        const uid = `dv-${Math.random().toString(36).slice(2, 9)}`;
        const gain = nominal > 0 ? (pxPerMm / (baseRadiusPx / nominal)).toFixed(0) : "—";

        const plotted = outlinePoints.map((sample) => {
            const angle = sampleAngle(sample, total);
            const value = Number(sample.value);
            const radiusPx = radiusPxForMeasurement(value);
            const point = polarToXY(cx, cy, radiusPx, angle);
            return { sample, angle, value, radiusPx, point, isMin: false, isMax: false };
        });

        const outline = plotted.map((p) => `${p.point.x.toFixed(2)},${p.point.y.toFixed(2)}`).join(" ");

        const minDiameter = diameterSamples.find(
            (sample) => sample.index === minIndex || (minIndex == null && Number(sample.value) === minVal)
        );
        const maxDiameter = diameterSamples.find(
            (sample) => sample.index === maxIndex || (maxIndex == null && Number(sample.value) === maxVal)
        );

        function diameterMarkerPlot(sample, kind) {
            if (!sample) return null;
            const angle = sampleAngle(sample, diameterSamples.length || total);
            const markerRadius = outlineMode === "radius" ? minVal / 2 : Number(sample.value);
            const markerValue = Number(sample.value);
            if (outlineMode === "radius" && kind === "max") {
                return {
                    sample,
                    angle,
                    value: maxVal,
                    point: polarToXY(cx, cy, radiusPxForMeasurement(maxVal / 2), angle),
                    isMin: kind === "min",
                    isMax: kind === "max",
                };
            }
            if (outlineMode === "radius" && kind === "min") {
                return {
                    sample,
                    angle,
                    value: minVal,
                    point: polarToXY(cx, cy, radiusPxForMeasurement(minVal / 2), angle),
                    isMin: kind === "min",
                    isMax: kind === "max",
                };
            }
            return {
                sample,
                angle,
                value: markerValue,
                point: polarToXY(cx, cy, radiusPxForMeasurement(markerRadius), angle),
                isMin: kind === "min",
                isMax: kind === "max",
            };
        }

        const minPlot = diameterMarkerPlot(minDiameter, "min");
        const maxPlot = diameterMarkerPlot(maxDiameter, "max");
        if (minPlot) minPlot.isMin = true;
        if (maxPlot) maxPlot.isMax = true;

        const markerPlots = [minPlot, maxPlot].filter(Boolean);
        const markerDots = markerPlots
            .map((p) => {
                const cls = p.isMin ? "diameter-viz-point min" : "diameter-viz-point max";
                const label = p.isMin
                    ? `<title>Min D${p.sample.index}: ${fmt(p.value, digits)} mm @ ${fmt(p.angle, 0)}°</title>`
                    : `<title>Max D${p.sample.index}: ${fmt(p.value, digits)} mm @ ${fmt(p.angle, 0)}°</title>`;
                return `${label}<circle class="${cls}" cx="${p.point.x.toFixed(2)}" cy="${p.point.y.toFixed(2)}" r="${markerDotSize}" />`;
            })
            .join("\n");

        const outlineDots = plotted
            .map((p) => {
                const label = `<title>R${p.sample.index}: ${fmt(p.value, digits)} mm @ ${fmt(p.angle, 0)}°</title>`;
                return `${label}<circle class="diameter-viz-point" cx="${p.point.x.toFixed(2)}" cy="${p.point.y.toFixed(2)}" r="${dotSize}" />`;
            })
            .join("\n");

        function markerLabel(plot, kind) {
            if (!plot) return "";
            const raw = radialOffset(cx, cy, plot.point, labelOffset);
            // Keep labels inside the SVG so side MIN/MAX text is not clipped.
            const x = Math.max(labelMargin, Math.min(size - labelMargin, raw.x));
            const y = Math.max(labelMargin + labelSize, Math.min(size - labelMargin - subLabelSize, raw.y));
            const anchor = x >= cx ? "start" : "end";
            const lineGap = Math.round(subLabelSize * 1.2);
            return `
                <text class="diameter-viz-label ${kind}" x="${x.toFixed(1)}" y="${(y - 4).toFixed(1)}" text-anchor="${anchor}" font-size="${labelSize}px">
                    ${kind === "min" ? "MIN" : "MAX"} ${fmt(plot.value, digits)} mm
                </text>
                <text class="diameter-viz-label-sub ${kind}" x="${x.toFixed(1)}" y="${(y + lineGap).toFixed(1)}" text-anchor="${anchor}" font-size="${subLabelSize}px">
                    ${fmt(plot.angle, 0)}° · S${plot.sample.index}
                </text>
            `;
        }

        const passClass = result.pass ? "pass" : "fail";
        const tir = fmt(tirMm, digits);

        container.innerHTML = `
            <div class="diameter-viz ${passClass}">
                ${title ? `<div class="diameter-viz-title">${title}</div>` : ""}
                <svg class="diameter-viz-svg" viewBox="0 0 ${size} ${size}" width="${size}" height="${size}" role="img" aria-label="Diameter cross-section visualizer">
                    <defs>
                        <radialGradient id="${uid}-bg" cx="50%" cy="50%" r="50%">
                            <stop offset="0%" stop-color="#ffffff" />
                            <stop offset="100%" stop-color="#edf5f1" />
                        </radialGradient>
                    </defs>
                    <rect x="0" y="0" width="${size}" height="${size}" fill="url(#${uid}-bg)" rx="12" />
                    <circle class="diameter-viz-body" cx="${cx}" cy="${cy}" r="${nominalR.toFixed(2)}" />
                    <circle class="diameter-viz-tolerance-band" cx="${cx}" cy="${cy}" r="${tolOuterR.toFixed(2)}" />
                    <circle class="diameter-viz-tolerance-band inner" cx="${cx}" cy="${cy}" r="${tolInnerR.toFixed(2)}" />
                    <circle class="diameter-viz-nominal" cx="${cx}" cy="${cy}" r="${nominalR.toFixed(2)}" />
                    <polygon class="diameter-viz-outline" points="${outline}" />
                    ${outlineDots}
                    ${markerDots}
                    ${markerLabel(minPlot, "min")}
                    ${markerLabel(maxPlot, "max")}
                    <circle class="diameter-viz-center" cx="${cx}" cy="${cy}" r="2" />
                </svg>
                ${
                    showLegend
                        ? `<div class="diameter-viz-legend">
                            <span><i class="swatch nominal"></i>Target Ø ${fmt(nominalDiameter, digits)} mm</span>
                            <span><i class="swatch tol"></i>±${fmt(tolerance, digits)} mm</span>
                            <span><i class="swatch tir"></i>TIR ${tir} mm</span>
                            <span>Deviation ×${gain}</span>
                        </div>`
                        : ""
                }
            </div>
        `;
    }

    global.renderDiameterViz = renderDiameterViz;
})(typeof window !== "undefined" ? window : globalThis);
