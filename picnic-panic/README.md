# Picnic Panic

A picnic-themed tower defense game. Ants, beetles and wasps march down a dirt trail toward
your basket. Line the trail with defenders and keep them off the sandwiches for 20 waves.

The whole game is one file, `index.html`, with no build step and no dependencies.

## Play on a computer

Open `index.html` in a browser.

## Play on an iPhone

There are two ways. The first needs no Mac.

### Option 1: Add to Home Screen (no Mac needed)

1. Turn on GitHub Pages for this repo: **Settings → Pages → Build and deployment → Deploy from
   a branch**, choose `master` and `/ (root)`, then save.
2. After a minute the game is live at `https://ryanefoley.github.io/repo1/picnic-panic/`.
3. Open that link in **Safari** on the iPhone, tap **Share → Add to Home Screen**.

It launches full screen from its own icon and keeps working offline after the first visit.

### Option 2: Native app with Xcode (needs a Mac)

The `ios/` folder holds a small SwiftUI app that runs the same `index.html` full screen in
landscape. The project reads `index.html` and `fonts/` straight from this folder, so there
is only one copy of the game.

1. Open `ios/PicnicPanic.xcodeproj` in Xcode 15 or newer.
2. Select the **PicnicPanic** target → **Signing & Capabilities**, pick your Apple ID under
   **Team**. If Xcode says the bundle ID is taken, change `com.ryanefoley.picnicpanic` to
   anything unique.
3. Plug in the iPhone, choose it as the run destination and press **Run**.
4. The first time, on the phone go to **Settings → General → VPN & Device Management** and
   trust your developer certificate.

With a free Apple ID the app has to be re-installed from Xcode every 7 days. A paid Apple
Developer account removes that limit and allows TestFlight or the App Store.

## How to play

- Pick a defender, then tap the grass beside the trail. On a touch screen, tap once to preview
  and tap the same square again to place it.
- Tap a placed defender to upgrade it (twice), sell it for 70% back, or choose what it aims at.
- Sending a wave before the last one is cleared earns bonus crumbs.

| Defender | Cost | Good at |
| --- | --- | --- |
| Pea Slingshot | 25 | Cheap, quick single shots |
| Pepper Shaker | 40 | Slows every bug nearby (wasps only half) |
| Fly Swatter | 55 | Hits a cluster at once, double damage on wasps |
| Magnifier | 80 | Sunbeam that heats up on one bug and ignores armor |

Keyboard: `1`–`4` pick a defender, `Esc` cancel, `U` upgrade, `Del` sell, `N` next wave,
`F` speed, `Space` pause.

## Files

```
index.html             the game
manifest.webmanifest   home-screen app settings
sw.js                  offline cache (bump CACHE when files change)
icons/                 home-screen icons
fonts/                 bundled Bagel Fat One and Figtree (SIL OFL)
ios/                   Xcode project for the native app
```
