# Device test: does the lock really work?

Two builds, two tests. **Front mode** (scheme `QuietHoursFront`) installs on the free Personal Team today. **Screen Time mode** (scheme `QuietHours`) needs a paid developer team. Everything below is on the debug screen ("Lock engine (debug)"). An iPhone on iOS 26.0 or later.

## Front mode (free team, about 15 minutes)

### Before you start

- Face ID or Touch ID turned on for unlocking the phone. Without it, locking the phone may count as stepping out (see LOCK-NOTES.md, "Front mode"); the debug screen shows a red warning if so.
- Plug in, unlock, trust the Mac. If Developer Mode is off: Settings > Privacy & Security > Developer Mode.
- Free-team builds: the first time, iOS may ask you to trust the developer in Settings > General > VPN & Device Management. The profile lasts 7 days; after that, run from Xcode again.

### First run: lock, glance, step out (5-minute window)

1. **Run.** Open `ios/QuietHours.xcodeproj`, scheme **QuietHoursFront**, your iPhone as destination, Run. The team is already set and signs.
2. **Check the mode.** The top of the debug screen says *Mode compiled in* `front`. Tap *Allow notifications*, allow. Expect *Access* `nothing to grant (front mode)`, *Notifications* `allowed`, *Lock signal* `reliable (Face ID / Touch ID on)`.
3. **Start.** Tap *Start 5-minute test window, 1 minute from now*. Expect *Phase* `scheduled` and a "Quiet hours" notification within about 5 seconds.
4. **Be in.** Stay in Quiet Hours through the start. Expect *Phase* `active`, *In front since* = the start time, and the countdown on the Lock Screen / Dynamic Island.
5. **Lock.** Press the side button. Wait 30 seconds. Unlock; you should land back in Quiet Hours.
   Expect: no "stepped out" notification, *Reach count* `0`, *Not counted: lock* `1`, and a log line `phone locked, decided Ns after leaving: not counted`. **Write down N** (expected about 10).
6. **Glance.** Swipe home, open any app, come back within 10 seconds. Expect *Reach count* `1`, no notification.
7. **Not counted.** Pull down Control Center and close it. Pull down Notification Center and close it. Swipe up and hold to show the app switcher, then tap Quiet Hours. Expect *Reach count* still `1`. Note if any of these counted.
8. **Step out and come back.** Swipe home, open another app, stay there.
   - About 17 seconds after leaving, a notification should say you stepped out, how long you have, and the time to be back by.
   - The Dynamic Island / Lock Screen should switch to "Stepped out. Back by …" with a countdown.
   - Come back to Quiet Hours before that time. Expect *Reach count* `2`, *Phase* `active`, and the Live Activity back to the window countdown. The notification should be gone from Notification Center.

### Second run: not coming back (5-minute window)

9. Tap *Cancel window*, then start a new test window and stay in Quiet Hours through its start.
10. Within the first minute, go to another app and stay out for 3 minutes. Don't open Quiet Hours.
    - Expect the notification at about 17 seconds.
    - When the back-by time passes, the Live Activity should read "You left quiet hours" (untested: depends on iOS redrawing a stale activity).
11. Open Quiet Hours. Expect *Phase* `left`, *Left early at* = the back-by time (2 minutes after you left), *Lock removed* `… by front (not back in time)`, and the Live Activity gone.

### Optional

- **Call** (needs a second phone). With Quiet Hours in front during a window, receive a call and answer it full screen. Hang up. Expect `phone call … not counted`. Note which app iOS returned you to after hanging up.
- **Force-quit.** During a window, swipe up and close Quiet Hours. Reopen it within 2 minutes. Expect a reach counted and *Phase* `active`.
- **Restart.** During a window, lock the phone, restart it, unlock, open Quiet Hours. Expect `phone restarted since leaving the front: not counted` (or `… while Quiet Hours was in front`).

### What to send back (front mode)

- N from step 5, and whether any lock counted as a reach.
- Whether step 7's gestures changed the reach count.
- When the notification arrived in steps 8 and 10, and its wording on screen.
- What the Live Activity showed in steps 8, 10 and 11.
- Where iOS returned you after a call, if you tried it.

## Screen Time mode (paid team, about 10 minutes)

### Before you start: you need a paid developer team

The current team, `AT9J4ACTP9` ("Hartley Scales"), is a free Personal Team. Xcode refuses to sign Family Controls for it:

> Personal development teams, including "Hartley Scales", do not support the Family Controls (Development) capability.

Apple's capability table agrees: Family Controls (development) is available to Apple Developer Program members only. So, before the steps below:

1. Use a team that is in the paid Apple Developer Program (enrol, or borrow a teammate's team).
2. In `ios/project.yml`, set `DEVELOPMENT_TEAM` to that team's id, then run `cd ios && xcodegen generate`.
3. If Xcode says a bundle id or the App Group "is not available": the Personal Team has registered `com.hms-web-development.QuietHours`, `com.hms-web-development.QuietHours.Widgets` and `group.com.hms-web-development.QuietHours`. In `project.yml` change `QH_BUNDLE_ID` and `QH_APP_GROUP` (for example to `…QuietHours2`) and regenerate. Every extension id follows `QH_BUNDLE_ID`; nothing else needs to change.

### Steps

1. **Plug in.** Connect the iPhone, unlock it, trust the Mac. If Developer Mode is off: Settings > Privacy & Security > Developer Mode.
2. **Select the team.** Open `ios/QuietHours.xcodeproj`. In Signing & Capabilities, the `QuietHours` app and its four extensions should show the paid team and no errors.
3. **Run.** Scheme **QuietHours**, your iPhone as destination, Run. Installing it replaces the front-mode build.
4. **Authorize.** Tap *Authorize (Screen Time + notifications)*. Approve with Face ID, then allow notifications.
   Expect: *Access* `Screen Time approved`, *Notifications* `allowed`.
5. **Pick what stays open.** *Lock scope* should read `lock all except what is picked` (the default). Tap *Choose apps to leave open*. In the picker, tick **Maps, Wallet and Camera** (expand their categories; note whether Phone is listed at all). Tap Done.
   Expect: *Selection* `3 apps, …`.
6. **Optional.** Tap + under *Shield subtitle count* a few times so the shield has a number to show.
7. **Start the test window.** Tap *Start 2-minute test window, 1 minute from now*.
   Expect: *Phase* `scheduled`, *DeviceActivity monitoring* `yes`, *Monitored interval* about 16 minutes long (the padding for DeviceActivity's 15-minute minimum), *Live Activity* `pending`. A "Quiet hours" notification arrives within about 5 seconds.
8. **Go to the home screen and keep using the phone.** iOS only calls the lock extension while the phone is in use. Don't sit in Quiet Hours itself: the app would apply the lock on its own and hide whether the extension did.
   At the start time, expect: almost every app's icon dims with an hourglass, and a countdown appears on the Lock Screen / Dynamic Island.
9. **Check what stayed open. This decides the default.** Open Maps, Wallet, Camera and Phone. Each should open with no shield. Also try Messages, Settings and Safari.
   - If a picked app shows a shield, note which. That is the "known issues" bug Apple acknowledged in 2024, and the default should switch to "lock only picked" (LOCK-NOTES.md, "Total lock").
10. **Open an app you didn't pick** (for example Photos). Check the shield: title `Quiet hours until <end time>`, a subtitle (with the count if you set one), buttons **Stay** and **Leave quiet hours**.
11. **Tap Stay.** The app should close. Wait 5 seconds, open it again: the shield is back.
12. **Tap Leave quiet hours.** The shield should go away and the app should be usable. If the shield redraws and stays up instead, note it.
13. **Check the numbers.** Open Quiet Hours. Expect:
    - *Phase* `left`, *Left early at* = when you tapped Leave
    - *Lock applied* `<start time> by monitor`
    - *Shield set (system)* `no`
    - *Reach count* `2`, *Shield draw requests (raw)* 2 or more, *Stay presses* `1`
    - *Live Activity* `none`, `ended` or `dismissed`

### Optional second run (3 minutes): "lock only picked", and the lock ends on its own

Set *Picks mean* to *Lock only picked* (this clears the picks), tap *Choose apps to lock*, pick one app you can open (not Settings or Phone), Done. Start another test window, open that app once to see the shield, then leave it alone. About 2 minutes after the start, the icon should un-dim. The log should show `monitor (short-window end): lock removed`. The Live Activity should read "Quiet hours are over".

### What to send back (Screen Time mode)

- Step 9: which of Maps, Wallet, Camera, Phone, Messages, Settings and Safari opened without a shield, and whether Phone appeared in the picker.
- Reach count, raw shield requests, and stay presses after step 13.
- Whether the log shows `monitor: intervalDidStart` and `lock applied ... by monitor`.
- The lines `monitor: ended N Live Activities` / `shield: ended N Live Activities`, and whether N was 0.
- Whether the shield's end time was right, and whether step 12 left the shield up.
- If reach count and raw requests both stayed at 0 although you saw the shield: the shield extension cannot write to shared storage, and the reach counter needs another approach.
