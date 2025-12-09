# Handsome Dan Loading Animation Update

## Overview
Replaced the dog emoji (🐕) with cycling Handsome Dan images during PDF upload processing.

## Changes Made

### 1. HTML Update (`frontend/index.html`)
- Changed from `<div class="bulldog">🐕</div>` to `<img>` element
- Added `id="handsomeDan"` for JavaScript control
- Set initial src to `images/handsome-dan-1.png`

### 2. CSS Update (`frontend/style.css`)
- Increased `.bulldog-container` height from 80px to 120px for better image display
- Updated `.bulldog` styling:
  - Changed from font-size to width/height (100px x 100px)
  - Added `object-fit: contain` to preserve image aspect ratio
  - Added centering with flexbox to container
- Updated `@keyframes walk`:
  - Adjusted positions for larger image size (-120px start/end)
  - Fixed transform for proper flipping with `translateX(50%)`
- Removed CSS `@keyframes cycleImages` (now handled by JavaScript)

### 3. JavaScript Update (`frontend/app.js`)
- Added image cycling logic in `uploadPdf()` function:
  - Creates interval that switches between two images every 1 second
  - Cycles through: `handsome-dan-1.png` ↔ `handsome-dan-2.png`
- Added `clearInterval(imageInterval)` in two places:
  - On successful upload completion
  - On error/timeout

## Image Files Needed

Save the two Handsome Dan images to `/frontend/images/`:

1. **handsome-dan-1.png** - First image (dark sweater, plain)
2. **handsome-dan-2.png** - Second image (with Y on sweater)

## Animation Behavior

When a PDF is being processed:
1. Handsome Dan walks from left to right across the screen
2. Images alternate every 1 second between the two poses
3. At the midpoint, Dan flips direction and walks back
4. Animation continues until upload completes or errors

## Testing

1. Save both Handsome Dan images to `/frontend/images/`
2. Refresh the browser (Cmd+Shift+R)
3. Upload a PDF file
4. Verify:
   - Images cycle every 1 second
   - Dan walks smoothly across the screen
   - Animation stops when upload completes
   - Images are properly sized and centered

## Technical Details

- **Image switching**: JavaScript `setInterval` every 1000ms
- **Walk animation**: CSS `@keyframes walk` over 3 seconds
- **Image size**: 100px x 100px with `object-fit: contain`
- **Direction**: Flips at 50% using `scaleX(-1)` transform
