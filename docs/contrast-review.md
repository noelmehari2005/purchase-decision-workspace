# Authored color contrast review — November 16, 2026

Scope: the opaque theme colors and adjacent surfaces declared in `frontend/src/styles.css`, including primary/neutral hover, error/notice, eligibility, cost display, editable boundaries and focus. Ratios use WCAG sRGB relative luminance. All text uses the conservative 4.5:1 threshold; component boundaries and authored focus use 3:1.

[W3C text-contrast guidance](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum) and [non-text contrast guidance](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast).

The original input border `#c8d1c8` measured 1.57:1 against white. It was replaced with `#7b8c80`, measuring 3.56:1. Chrome computed styles confirmed the new border on the RAM input. Decorative separators and card outlines are not treated as input boundaries. Text labels and the current-step marker also communicate state; eligibility is not communicated by color alone.

| Component / surface | Foreground | Background | Ratio | Threshold | Result |
| --- | --- | --- | ---: | ---: | --- |
| Body text / page | `#20312d` | `#f5f6f2` | 12.57:1 | 4.5:1 | Pass |
| Body text / paper | `#20312d` | `#ffffff` | 13.65:1 | 4.5:1 | Pass |
| Muted text / paper | `#5c6b64` | `#ffffff` | 5.61:1 | 4.5:1 | Pass |
| Muted text / page | `#5c6b64` | `#f5f6f2` | 5.17:1 | 4.5:1 | Pass |
| Muted text / import and scenario | `#5c6b64` | `#f6f8f3` | 5.25:1 | 4.5:1 | Pass |
| Muted text / review | `#5c6b64` | `#f4f7f1` | 5.19:1 | 4.5:1 | Pass |
| Muted text / notice | `#5c6b64` | `#f0f2e9` | 4.97:1 | 4.5:1 | Pass |
| Muted text / error | `#5c6b64` | `#fff0ec` | 5.06:1 | 4.5:1 | Pass |
| Link / paper | `#17624f` | `#ffffff` | 7.25:1 | 4.5:1 | Pass |
| Link / page | `#17624f` | `#f5f6f2` | 6.68:1 | 4.5:1 | Pass |
| Link / import | `#17624f` | `#f6f8f3` | 6.78:1 | 4.5:1 | Pass |
| Link / notice | `#17624f` | `#f0f2e9` | 6.42:1 | 4.5:1 | Pass |
| Primary button and brand text | `#ffffff` | `#17624f` | 7.25:1 | 4.5:1 | Pass |
| Primary hover text | `#ffffff` | `#104b3c` | 10.03:1 | 4.5:1 | Pass |
| Danger button text | `#ffffff` | `#8a3131` | 8.19:1 | 4.5:1 | Pass |
| Neutral button text | `#20312d` | `#ffffff` | 13.65:1 | 4.5:1 | Pass |
| Neutral hover text | `#20312d` | `#edf3ec` | 12.11:1 | 4.5:1 | Pass |
| Current step text | `#174f3d` | `#e1ebe1` | 7.73:1 | 4.5:1 | Pass |
| Step number text | `#ffffff` | `#17624f` | 7.25:1 | 4.5:1 | Pass |
| Prototype note | `#4d5e50` | `#edf0e9` | 6.02:1 | 4.5:1 | Pass |
| Notice text | `#4e5a47` | `#f0f2e9` | 6.46:1 | 4.5:1 | Pass |
| Error text | `#9f302d` | `#fff0ec` | 6.45:1 | 4.5:1 | Pass |
| Draft badge | `#4b5d52` | `#edf0ea` | 6.11:1 | 4.5:1 | Pass |
| Requirements met badge | `#1d6142` | `#e1efe4` | 6.22:1 | 4.5:1 | Pass |
| Requirements failed badge | `#8d3d2e` | `#f5e8e3` | 6.18:1 | 4.5:1 | Pass |
| Needs verification badge | `#735a22` | `#f5efdc` | 5.68:1 | 4.5:1 | Pass |
| Count text | `#20312d` | `#e5ebe1` | 11.25:1 | 4.5:1 | Pass |
| Advantages text | `#20312d` | `#f0f6ec` | 12.41:1 | 4.5:1 | Pass |
| Fit text | `#17624f` | `#ffffff` | 7.25:1 | 4.5:1 | Pass |
| Input border / white interior | `#7b8c80` | `#ffffff` | 3.56:1 | 3:1 | Pass |
| Input border / page | `#7b8c80` | `#f5f6f2` | 3.28:1 | 3:1 | Pass |
| Input border / scenario and import | `#7b8c80` | `#f6f8f3` | 3.33:1 | 3:1 | Pass |
| Input border / error | `#7b8c80` | `#fff0ec` | 3.21:1 | 3:1 | Pass |
| Focus / paper | `#2f6fb6` | `#ffffff` | 5.16:1 | 3:1 | Pass |
| Focus / page | `#2f6fb6` | `#f5f6f2` | 4.75:1 | 3:1 | Pass |
| Focus / import and scenario | `#2f6fb6` | `#f6f8f3` | 4.83:1 | 3:1 | Pass |
| Focus / notice | `#2f6fb6` | `#f0f2e9` | 4.57:1 | 3:1 | Pass |
| Focus / error | `#2f6fb6` | `#fff0ec` | 4.65:1 | 3:1 | Pass |
| Focus / current step | `#2f6fb6` | `#e1ebe1` | 4.22:1 | 3:1 | Pass |
| Cost bar / track | `#537d65` | `#ecf0e8` | 4.05:1 | 3:1 | Pass |

Limitations: this is an authored-theme review, not full WCAG certification. Disabled controls are excluded from contrast thresholds. Native select arrows, checkboxes, browser/OS forced colors, autofill and provider-hosted login/recovery screens require rendered checks in their actual environments. Transparent backgrounds inherit the surrounding surface; the table is not an exhaustive pixel or browser-state audit. Functional keyboard and spoken-output results are recorded separately in milestone 8.
