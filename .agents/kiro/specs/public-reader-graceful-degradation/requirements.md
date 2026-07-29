# Reader Asset Boundary Requirements

## Goal

Resolve DEBT-117 with one consistent public-reader missing-asset contract.

## Requirements

1. Chapter, novel detail, and library routes degrade locally for missing covers/assets.
2. One shared `ReaderAssetBoundary` owns equivalent fallback, accessibility, and logging behavior, or direct tests prove current shared boundaries are equivalent.
3. Missing assets never expose backend details or collapse readable text.
4. Fallbacks are keyboard/screen-reader safe and avoid duplicate landmarks.
5. Development logging remains sanitized; production output is quiet and safe.

## Out of Scope

New CDN/image pipeline, direct storage serving, generated reader downloads, and visual redesign.
