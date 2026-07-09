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

        const nominal = Number(result.nominal ?? opts.nominal ?? 0);
        const tolerance = Number(result.tolerance ?? opts.tolerance ?? 0);
        const samples = normalizeSamples(result);
        const total = samples.length || Number(opts.totalSamples) || 1;

        if (!samples.length) {
            container.innerHTML = '<div class="diameter-viz-empty">No sample data</div>';
            return;
        }

        const values = samples.map((s) => Number(s.value));
        const minVal = Number(result.min ?? Math.min(...values));
        const maxVal = Number(result.max ?? Math.max(...values));
        const minIndex = result.min_sample_index;
        const maxIndex = result.max_sample_index;
        const tirMm = Number(result.tir ?? maxVal - minVal);

        const cx = size / 2;
        const cy = size / 2;
        const maxRadiusPx = (size - pad * 2) / 2;

        // Amplify small diameter deviations so ±0.2–0.5 mm is visible on the outline.
        // Nominal sits at ~70% of the drawable radius; the remaining band is for deviation.
        const baseRadiusPx = maxRadiusPx * 0.7;
        const ampBandPx = maxRadiusPx * 0.28;
        const peakAbsDevMm = Math.max(
            Math.abs(maxVal - nominal),
            Math.abs(minVal - nominal),
            tirMm / 2,
            tolerance,
            MIN_DEVIATION_WINDOW_MM
        );
        const pxPerMm = ampBandPx / peakAbsDevMm;

        function radiusPxForDiameter(diameterMm) {
            const amplified = baseRadiusPx + (Number(diameterMm) - nominal) * pxPerMm;
            return Math.max(maxRadiusPx * 0.18, Math.min(maxRadiusPx, amplified));
        }

        const nominalR = radiusPxForDiameter(nominal);
        const tolOuterR = radiusPxForDiameter(nominal + tolerance);
        const tolInnerR = radiusPxForDiameter(Math.max(nominal - tolerance, 0));
        const uid = `dv-${Math.random().toString(36).slice(2, 9)}`;
        const gain = nominal > 0 ? (pxPerMm / (baseRadiusPx / (nominal / 2))).toFixed(0) : "—";

        const plotted = samples.map((sample) => {
            const angle = sampleAngle(sample, total);
            const value = Number(sample.value);
            const radiusPx = radiusPxForDiameter(value);
            const point = polarToXY(cx, cy, radiusPx, angle);
            const isMin = sample.index === minIndex || (minIndex == null && value === minVal);
            const isMax = sample.index === maxIndex || (maxIndex == null && value === maxVal);
            return { sample, angle, value, radiusPx, point, isMin, isMax };
        });

        const outline = plotted.map((p) => `${p.point.x.toFixed(2)},${p.point.y.toFixed(2)}`).join(" ");

        const sampleDots = plotted
            .map((p) => {
                const cls = p.isMin ? "diameter-viz-point min" : p.isMax ? "diameter-viz-point max" : "diameter-viz-point";
                const label = p.isMin
                    ? `<title>Min S${p.sample.index}: ${fmt(p.value, digits)} mm @ ${fmt(p.angle, 0)}°</title>`
                    : p.isMax
                      ? `<title>Max S${p.sample.index}: ${fmt(p.value, digits)} mm @ ${fmt(p.angle, 0)}°</title>`
                      : `<title>S${p.sample.index}: ${fmt(p.value, digits)} mm @ ${fmt(p.angle, 0)}°</title>`;
                const r = p.isMin || p.isMax ? markerDotSize : dotSize;
                return `${label}<circle class="${cls}" cx="${p.point.x.toFixed(2)}" cy="${p.point.y.toFixed(2)}" r="${r}" />`;
            })
            .join("\n");

        const minPlot = plotted.find((p) => p.isMin);
        const maxPlot = plotted.find((p) => p.isMax);

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
                    ${sampleDots}
                    ${markerLabel(minPlot, "min")}
                    ${markerLabel(maxPlot, "max")}
                    <circle class="diameter-viz-center" cx="${cx}" cy="${cy}" r="2" />
                </svg>
                ${
                    showLegend
                        ? `<div class="diameter-viz-legend">
                            <span><i class="swatch nominal"></i>Nominal Ø ${fmt(nominal, digits)} mm</span>
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
