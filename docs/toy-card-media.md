# Desktop toy card media

The catalog uses a 640 × 400 WebP preview and a 32 × 32 SVG icon for each stable application key. Keep the existing toy_defender identity for Abduction so grants and URLs remain valid.

Previews were captured from actual running toys in dwiest/wiest-desktop-toys on November 18, 2026, using Chromium at a 1100 × 800 viewport after an initial warm-up. Abduction uses a frame at 120 seconds, Missile Command at 90 seconds, and Ms. Pac-Man and Pixel Fireworks at 45 seconds; these replace their early captures. The remaining toys use about ten seconds of playback. Capture the canvas (the stage for the layered Spinning Sticks canvases), preserve its aspect ratio, and pad to 640 × 400 with #080d18. Fireworks uses the Festival preset with 18 launches per minute and three shells per launch. Convert to WebP at quality 84. 

Existing header marks are reused for Spinning Sticks, Tidal, Plinko, Pixel Fireworks, and Abduction. Arcade icons use their gameplay bitmap sprites where available; Ms. Pac-Man and Missile Command have matching vector symbols.

Files live under static/dwiest-django-demos/toy-previews/<application_key>.webp and toy-icons/<application_key>.svg. Add both when adding a toy. Regenerate a preview after a major gameplay visual change. These assets contain gameplay only, with no account/session information.

The .toy-preview area has a stable 8:5 ratio. A future short clip can use the existing image as its video poster; keep playback opt-in or respect reduced-motion preferences. No videos or live game embeds load with the current catalog.

After updating the package, run collectstatic as usual so the new image assets are served.
