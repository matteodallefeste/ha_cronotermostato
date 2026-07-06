# Brand images

Placeholder (all-black) icons for the Weekly Thermostat integration.

## How icons are loaded (HA 2026.3+)

Since Home Assistant **2026.3** custom integrations can ship their brand
images locally, and these take **priority over the brands CDN**. The images
that actually make the logo/icon appear in the UI live in:

```
custom_components/weekly_thermostat/brand/
├── icon.png       # 256x256
├── icon@2x.png    # 512x512
├── logo.png       # 256x256
└── logo@2x.png    # 512x512
```

No submission to any external repository is required for the icons to show up.
See the [Brands proxy API announcement](https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api/).

## This `brands/` folder

The files under `brands/custom_integrations/weekly_thermostat/` are just a
**staging copy** kept for an optional future submission to the
[home-assistant/brands](https://github.com/home-assistant/brands) repository
(which the HACS `brands` validation check looks at). It is not loaded by Home
Assistant at runtime. When you replace the placeholder artwork, update both
this staging copy and the `custom_components/weekly_thermostat/brand/` folder.

## Files

| File          | Size    | Notes                                  |
| ------------- | ------- | -------------------------------------- |
| `icon.png`    | 256x256 | Square icon (required)                 |
| `icon@2x.png` | 512x512 | hDPI icon (required alongside `icon`)  |
| `logo.png`    | 256x256 | Logo (optional)                        |
| `logo@2x.png` | 512x512 | hDPI logo (optional)                   |

## Requirements

- PNG with transparency, trimmed of surrounding whitespace.
- `icon.png` must be square, between 128x128 and 256x256.
- `@2x` variants must be exactly double the base dimensions.
- Optional dark-theme variants: `dark_icon.png`, `dark_logo.png` (+ `@2x`).
