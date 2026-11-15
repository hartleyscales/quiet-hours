# Lock engine notes

Written 2026-11-14 against Xcode 27.2 and the iOS 27.2 SDK. Updated the same day with a second lock mode (front mode) and a "lock everything except" option for Screen Time mode. Everything here compiles. **Nothing has run on a phone yet**: see "Build record".

## Two modes, one engine

The lock mode is chosen at compile time, by scheme. Both schemes build the same app (same bundle id, same App Group), so installing one replaces the other.

| Scheme | Mode | Signs on the free Personal Team? |
|---|---|---|
| `QuietHours` | **Screen Time.** Apple's shield over locked apps. App + four Screen Time extensions + widgets. | No. Family Controls needs a paid team. |
| `QuietHoursFront` | **Front.** Quiet Hours stays in front during the window; going to another app counts as a reach. App + widgets only. | Yes. Signed successfully (see "Build record"). |

A UI talks only to `QuietHoursEngine`; the same calls work in both modes (see "What the future UI calls"). The mode-specific part sits behind the `LockBackend` protocol (`App/Engine/LockBackend.swift`): `ScreenTimeLock` in `App/Engine/ScreenTime/`, `FrontLock` in `App/Engine/Front/`. The front scheme compiles only the `Front` folder and sets the `QH_FRONT_MODE` compilation condition, which picks the backend in one place (`typealias ActiveLock`).

## What is in `ios/`

| Target | Kind | In scheme | Job |
|---|---|---|---|
| `QuietHours` | app | `QuietHours` | Screen Time mode: the engine and the debug screen. |
| `QuietHoursFront` | app | `QuietHoursFront` | Front mode: the same engine and debug screen. No Family Controls. |
| `QuietHoursMonitor` | DeviceActivity monitor extension | `QuietHours` | Applies the lock at the window's start and removes it at the end, with the app closed. |
| `QuietHoursShieldConfiguration` | Shield configuration extension | `QuietHours` | Title, subtitle and button labels on the shield. Counts reaches. |
| `QuietHoursShieldAction` | Shield action extension | `QuietHours` | Stay closes the app. Leave quiet hours removes the lock and records the time. |
| `QuietHoursWidgets` | Widget extension | both | The Live Activity countdown. |

Settings set once in `project.yml`: `DEVELOPMENT_TEAM` (the team, for every target), `QH_BUNDLE_ID` (the app's bundle id; extensions append to it), `QH_APP_GROUP` (`group.com.hms-web-development.QuietHours`). The two app targets' generated Info.plists and entitlements are in `Config/`. Shared code: `Shared/Core` (storage, window, phase; both modes), `Shared/ScreenTime` (lock targets, shield operations, shield copy; Screen Time only), `Shared/Activity` (Live Activity types; both).

Minimum iOS is **26.0**. iOS 26 added scheduled Live Activities: the app, while open, can ask for a Live Activity that the system starts at a future date. That is the only way, without push, to have the countdown appear when the window starts with the app closed. iOS 26 runs on iPhone 11 and later. Newer features (26.4 shield submenu, 26.5 open-app response and token refresh) are behind `#available` checks.

## How a window runs (Screen Time mode)

1. **Schedule** (app open). `scheduleWindow(id:start:end:)` stores the window in shared storage and starts one DeviceActivity schedule pinned to those calendar dates. It also schedules the notification 5 minutes before the start and the Live Activity for the start time, and asks for a background refresh at the end.
2. **Start** (app closed). iOS calls the monitor's `intervalDidStart`, which applies the shield from the stored tokens.
3. **Shield met.** iOS asks the shield configuration extension for content. The extension reads the end time and people count from shared storage and adds to the reach count.
4. **Stay.** The press is counted and the locked app closes.
5. **Leave.** The shield action extension clears the lock and records `leftAt`. It then tries to end the Live Activity.
6. **End** (app closed). iOS calls `intervalDidEnd` and the monitor clears the lock. Windows under 15 minutes end through `intervalWillEndWarning` instead (see limits).
7. **Next app launch.** The app fixes anything the extensions could not: a lock still on after the end, a Live Activity still showing.

## Checked against Apple's documentation (Screen Time mode)

Sources: Apple's documentation pages linked below, and the Swift interfaces in the iOS 27.2 SDK, which show exactly what compiles.

### Your three assumptions

1. **"Development builds can use Family Controls without Apple's distribution approval."** True only with a paid Apple Developer Program team. The distribution request is needed only for TestFlight and the App Store, and it must be made separately for the app and for each extension. A free Personal Team cannot sign Family Controls at all. Apple's [supported capabilities table](https://developer.apple.com/help/account/reference/supported-capabilities-ios) ticks "Family Controls (development)" for ADP only, not for ADEP or a free Apple Developer account. Xcode gave the same answer for this project (see "Build record"). The current team, `AT9J4ACTP9`, is a Personal Team. See also [Requesting the Family Controls entitlement](https://developer.apple.com/documentation/familycontrols/requesting-the-family-controls-entitlement) and the [entitlement](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.developer.family-controls).
2. **"The shield is a fixed template."** Confirmed. [`ShieldConfiguration`](https://developer.apple.com/documentation/managedsettingsui/shieldconfiguration) has only: background blur style, background colour, icon, title, subtitle, primary button label and background colour, and secondary button label. Every field left nil gets the system default. iOS 26.4 added one thing: [`secondaryButtonSubmenuItems`](https://developer.apple.com/documentation/managedsettingsui/shieldconfiguration/secondarybuttonsubmenuitems), up to three menu items behind the secondary button. Nothing else can be drawn.
3. **"A shield action cannot open the main app."** Out of date. This was true until iOS 26.5, which added [`ShieldActionResponse.openParentalControlsApp`](https://developer.apple.com/documentation/managedsettings/shieldactionresponse/openparentalcontrolsapp), documented as opening the app that set the shield. It is in the 27.2 SDK. The other responses are still `close`, `defer` and `none` ([`ShieldActionResponse`](https://developer.apple.com/documentation/managedsettings/shieldactionresponse)). I wired it behind a switch, off by default: on 26.5+, *Leave quiet hours* can open Quiet Hours so it reports the leave immediately. Whether that is the right experience is a design question. **Untested.** I have not confirmed that it works with individual (self) authorization; the docs say "parental controls app" without separating individual from child.

### Each capability

| Capability | Status | Source |
|---|---|---|
| Individual authorization and its status | Confirmed. `requestAuthorization(for: .individual)` shows a Face ID prompt. `authorizationStatus` is `notDetermined`, `denied`, `approved`, or `approvedWithDataAccess` (26.4). | [requestAuthorization(for:)](https://developer.apple.com/documentation/familycontrols/authorizationcenter/requestauthorization(for:)) |
| Apple's picker, persisted for extensions | Confirmed. `FamilyActivitySelection` is Codable and holds opaque tokens. We store the tokens as JSON in the App Group. Revoking authorization voids them. | [FamilyActivitySelection](https://developer.apple.com/documentation/familycontrols/familyactivityselection) |
| Lock starts and stops with the app closed | Confirmed, with limits (below). The monitor extension gets `intervalDidStart` and `intervalDidEnd`. | [DeviceActivityMonitor](https://developer.apple.com/documentation/deviceactivity/deviceactivitymonitor) |
| Apply and remove the lock | Confirmed. A named `ManagedSettingsStore` is shared by the app and its extensions. We set `shield.applications`, categories and web domains, and clear them with `clearAllSettings()`. | [ManagedSettingsStore](https://developer.apple.com/documentation/managedsettings/managedsettingsstore) |
| Leave early from the shield | Confirmed that the shield action extension gets the secondary-button press and can change the store. | [ShieldActionDelegate](https://developer.apple.com/documentation/managedsettings/shieldactiondelegate) |
| Shield content from shared storage | Confirmed that the extension can't use the network. Reading the App Group is expected to work. Writing to it is not documented (see "Reach counter"). | [ShieldConfigurationDataSource](https://developer.apple.com/documentation/managedsettingsui/shieldconfigurationdatasource) |
| Live Activity with the window | Partly. It can be *scheduled* to start at the window's start (iOS 26+, requested while the app is open, alert required). The app can end it, in the foreground or the background. Starting or ending it with the app closed otherwise needs push. | [request(...start:)](https://developer.apple.com/documentation/activitykit/activity/request(attributes:content:pushtype:style:alertconfiguration:start:)), [Activity](https://developer.apple.com/documentation/activitykit/activity), [Displaying live data](https://developer.apple.com/documentation/activitykit/displaying-live-data-with-live-activities) |
| Notification before the start | A standard local calendar notification. I didn't recheck the documentation for it. | UserNotifications |

I also checked the schedule maths against Apple's own code. A Mac Catalyst build of DeviceActivity computed `nextInterval` for our date-pinned schedules correctly: future, ongoing, crossing midnight, and already over (nil).

## Platform limits that affect the product (Screen Time mode)

Most important first.

1. **A paid developer team is required even to test on a phone.** The current team is free. See [DEVICE-TEST.md](DEVICE-TEST.md). Front mode exists because of this.
2. **Reaches cannot be counted exactly.** No API reports "the shield was shown." See "Reach counter" for what is counted instead.
3. **The lock starts on first use, not at the second.** iOS calls `intervalDidStart` "only when the device is in use" ([docs](https://developer.apple.com/documentation/deviceactivity/deviceactivitymonitor/intervaldidstart(for:))). A phone in a pocket locks the moment it is picked up inside the window. To the person this looks on time. `appliedAt` records when it actually happened.
4. **Windows shorter than 15 minutes need a workaround.** DeviceActivity rejects intervals under 15 minutes ([`intervalTooShort`](https://developer.apple.com/documentation/deviceactivity/deviceactivitycenter/monitoringerror/intervaltooshort)). Over a week is also rejected ([`intervalTooLong`](https://developer.apple.com/documentation/deviceactivity/deviceactivitycenter/monitoringerror/intervaltoolong)). The engine pads short windows to 16 minutes and sets the warning time so that `intervalWillEndWarning` fires at the real end, where the monitor removes the lock. The 2-minute test window works this way. Real campus windows (hours) don't need it.
5. **The people count on the shield is only as fresh as the app's last write.** The shield extension has no network access, and the app is usually closed during the window. A shield already on screen is not redrawn when the number changes. A live number would need the monitor extension to fetch it, and it only runs at window boundaries.
6. **Live Activity end and leave need the app or push.** The monitor and shield action extensions try to end the Live Activity and log how many they found. A forum report ([thread 761577](https://developer.apple.com/forums/thread/761577)) says the monitor extension sees none, so expect 0. Without that:
   - The activity's stale date is the window's end, so the countdown reads "Quiet hours are over" at the end. Untested: this depends on iOS redrawing the activity when it goes stale. If it doesn't, the timer still stops at 0:00.
   - After leaving, it keeps counting down until the app runs.
   - The app ends it on next launch. A background refresh is also requested for the end time, but iOS decides if and when that runs.
   - The system removes any Live Activity after 8 hours active plus up to 4 on the Lock Screen.

   ActivityKit push from the server would make the start, the end and the leave exact.
7. **Leaving is recorded on the phone; reporting it to the server is not guaranteed to be immediate.** Leave from the shield runs in an extension with the app closed. Whether that extension may use the network is undocumented. Today `leftAt` waits in shared storage until the app next runs. On 26.5+, the "Leave opens the app" switch would make the report immediate.
8. **Leaving is not the only exit.** An individual can revoke Screen Time access in Settings, or delete the app, at any time. Apple removes the anti-tamper restrictions for individual authorization ([docs](https://developer.apple.com/documentation/familycontrols/authorizationcenter/requestauthorization(for:))). This probably removes the lock without any "left" record. The app can see `denied` / `notDetermined` on its next run, but not when it happened. The "Stayed" number can count such people as having stayed.
9. **Stored tokens can expire (iOS 26.5).** Apple added [`TokenExpiryMessage`](https://developer.apple.com/documentation/managedsettings/managedsettingsstore/tokenexpirymessage) and `ManagedSettingsStore.refresh(_:)`. The docs don't say when expiry happens. The engine refreshes the stored tokens each time the app becomes active and before the monitor applies the lock.
10. **The monitor extension has a memory limit of about 6 MB.** Developers report this ([thread 735454](https://developer.apple.com/forums/thread/735454)); Apple doesn't document it. That is why the monitor imports only DeviceActivity, ManagedSettings and ActivityKit, and stores tokens without FamilyControls.
11. **At most 20 monitored activities per app** ([`excessiveActivities`](https://developer.apple.com/documentation/deviceactivity/deviceactivitycenter/monitoringerror/excessiveactivities)). We use one.
12. **At most 50 tokens per shield setting**, including 50 exceptions in `.all(except:)` ([`all(except:)`](https://developer.apple.com/documentation/managedsettings/shieldsettings/activitycategorypolicy/all(except:)), [`shield.applications`](https://developer.apple.com/documentation/managedsettings/shieldsettings/applications-swift.property)). Developers report that going over shields nothing at all ([thread 733361](https://developer.apple.com/forums/thread/733361)). The engine refuses to schedule over the limit and won't re-apply a lock that breaks it.

## Reach counter (Screen Time mode): exactly what it counts

The contract wants "each time the shield is met." The only signal iOS gives us is a call into the shield configuration extension asking what to draw. The counter works like this:

- Every such request adds 1 to `reach.shieldRequests` (raw).
- A request adds 1 to `reach.count` when a window is in progress and not left, **and** the previous request was at least 3 seconds earlier.

So a reach is "iOS drew our shield, not within 3 seconds of the last time it did." It is wrong in three known ways, none measured yet:

- **Undercount** if iOS reuses a cached shield instead of asking again. A forum report ([thread 716340](https://developer.apple.com/forums/thread/716340)) says the configuration is requested when the shielded app is first launched, which suggests some caching.
- **Overcount** if iOS asks for reasons other than someone opening the app, such as the app switcher.
- **Zero** if the shield extension's sandbox blocks writes to the App Group. Forum reports disagree; writes through UserDefaults are said to work, SQLite is not ([thread 762431](https://developer.apple.com/forums/thread/762431)). If so, the only honest count left is presses of Stay and Leave (`stay.count` is already recorded).

The device test compares the count with what was actually done. Until then, show it as "times the lock screen appeared," not as an exact count of attempts.

## Total lock (Screen Time mode)

The owner now wants every app locked, with Phone, Maps, Wallet and Camera left open, plus whatever the person adds. Findings from Apple's documentation and Apple staff on the developer forums, checked 2026-11-14:

**1. Can an app lock everything and leave chosen apps open without the person picking them? No.**
- The shield takes exceptions only as app tokens: `shield.applicationCategories = .all(except: Set<ApplicationToken>)` ([applicationCategories](https://developer.apple.com/documentation/managedsettings/shieldsettings/applicationcategories-swift.property), [all(except:)](https://developer.apple.com/documentation/managedsettings/shieldsettings/activitycategorypolicy/all(except:))).
- Tokens come only from Apple's picker. `Application(bundleIdentifier:)` compiles, but an Apple Frameworks Engineer says tokens "are not generated when initializing applications via bundleID" ([thread 727075](https://developer.apple.com/forums/thread/727075), 2023). So the app cannot put Maps or Wallet in `except:` by itself.
- `application.blockedApplications` does take bundle ids and works with individual authorization ([thread 716519](https://developer.apple.com/forums/thread/716519)), but it hides and blocks apps; it cannot exempt one. Websites are the only thing exemptible by name (`webContent.blockedByFilter = .all(except: Set<WebDomain>)`), and that is a content filter, not our shield.

**2. What iOS never locks.**
- Documented by Apple: only the app that set the shield. "Your app is exempt from `.all`" ([applicationCategories](https://developer.apple.com/documentation/managedsettings/shieldsettings/applicationcategories-swift.property)). Apple also says the system "doesn't guarantee" the settings govern the device ([ManagedSettingsStore](https://developer.apple.com/documentation/managedsettings/managedsettingsstore)).
- Apple staff on the forums: there are "unblock-able" system apps under `.all`, including anything on the person's Screen Time "Always Allowed" list ([thread 727230](https://developer.apple.com/forums/thread/727230), 2023); apps authorized with FamilyControls are exempt ([thread 783310](https://developer.apple.com/forums/thread/783310), 2025); a DTS engineer called the resulting limits "by design" ([thread 793613](https://developer.apple.com/forums/thread/793613), 2025).
- Developer report only, same 2025 thread: under `.all`, Phone, Messages, FaceTime, Maps, Clock, Settings, Safari, Find My, Compass and Health stayed open; Camera, Photos, Weather, Measure and App Store were shielded. Wallet is not mentioned. Apple publishes no list, and I could not confirm whether "Always Allowed" still exists in iOS 27's Screen Time settings.
- For the owner's four: **Phone** is reported never locked, and is reported not to appear in the picker at all. **Maps** is reported never locked. **Camera** is reported locked, so the person must pick it. **Wallet**: no information; the person should pick it. None of this is documented; the device test checks it.

**3. What the person must do in Apple's picker to leave an app open.**
- Tick the app itself (inside its category), or tick a whole category. A whole category gives only a category token unless the selection was made with `includeEntireCategory: true` (Apple DTS, [thread 723821](https://developer.apple.com/forums/thread/723821); Frameworks Engineer, [thread 724419](https://developer.apple.com/forums/thread/724419); [includeEntireCategory](https://developer.apple.com/documentation/familycontrols/familyactivityselection/includeentirecategory)). Under "lock everything except", the engine opens the picker with `includeEntireCategory: true`, so ticking a category leaves all its apps open.
- At most 50 apps and 50 websites can be left open. A big category ticked whole can go over; the engine then refuses.
- Ticked websites are left open the same way (`webDomainCategories = .all(except:)`).
- Known problem: developers reported in 2024 that exceptions under `.all(except:)` were still shielded, and an Apple Frameworks Engineer replied "There are known issues in this area" ([thread 766766](https://developer.apple.com/forums/thread/766766), Nov 2024). I found no confirmed fix. **This is the main risk of total lock; the device test checks it first.**
- Also reported: the picker crashes when a category holds 200 or more tokens ("a known bug", [thread 764457](https://developer.apple.com/forums/thread/764457), 2024).

**What the engine does.** `LockTargets.scope` is either `.selected` ("lock what the person picked", the original behaviour) or `.allExcept` ("lock everything except what the person picked"). The scope is stored with the picks, because the same picks mean opposite things under the two. Changing the scope clears the picks. Under `.allExcept` the shield is `applicationCategories = .all(except: picked apps)` and `webDomainCategories = .all(except: picked sites)`, all in our one store (Apple staff: one store cannot make another less restrictive, [thread 724419](https://developer.apple.com/forums/thread/724419)). Picking nothing under `.allExcept` is allowed and locks everything iOS lets us lock.

**Default: `.allExcept` (lock everything except what the person picks).** Reasons: it is the owner's product decision; it is safe enough because every shield has *Leave quiet hours*, so nothing is truly out of reach; and Phone is reported to stay open regardless. Picks saved before the scope existed read as `.selected`, so they keep their meaning, and stored picks that cannot be read lock nothing rather than everything. The risk is the reported exception bug above: if it is still there on iOS 26/27, a person's Maps or Wallet would be locked despite being picked. If the device test shows that, switch the default to `.selected` (one line, `LockTargets.defaultScope`).

**What it changes in the contract.** CONTRACT.md says "The user chooses what locks once, in Apple's picker." Under total lock that becomes "chooses what stays open." The contract's "Calls and the user's chosen essentials stay open" already reads as total lock. I have not edited CONTRACT.md; it is shared with the server work.

## Front mode

### How it works

1. **Schedule.** Same call, same stored window, pre-start notification ("Open Quiet Hours then and leave it in front"), scheduled Live Activity and background refresh as Screen Time mode. No authorization is needed; notifications should be allowed.
2. **Start.** Nothing can force the app open. From the start until Quiet Hours is in front, the phase is `due`. The moment it is in front (or if it already was at the start), the person is in: `appliedAt` records when, `appliedBy` is `app (in front)`.
3. **Leaving the front.** When Quiet Hours goes to the background during the window, an absence starts (`undecided`). The app asks iOS for background time and, for 15 s (`frontLockDetectionWindow`), watches for a lock or a call. At the same moment it queues the stepped-out notification for 17 s.
4. **Decision.** Protected data going away within 15 s means the phone was locked (`lock`, not counted). A call ringing or connected means `call` (not counted). Either cancels the notification. Otherwise it is `out`: one reach, the notification goes out, and the Live Activity switches to "Stepped out. Back by 7:42" counting down the grace period.
5. **Coming back.** Quiet Hours in front again ends the absence and clears the notification. Back within the grace period (`frontGracePeriod`, 120 s from leaving) keeps the person in. A return before the decision with no lock or call seen is counted as an `out` too (a glance).
6. **Not coming back.** `leftAt` = the moment the grace period ran out. The app is suspended by then, so this is written the next time it runs (in the foreground, or at the window-end background refresh); the phase reads `left` as soon as it runs. If the window ends before the grace period would, nobody is marked as having left, and no notification is sent.
7. **Leave early, end, Live Activity.** `leaveEarly()` records `leftAt` and ends the Live Activity, as in Screen Time mode. At the end, `clearedAt` is set to the end time and the Live Activity is tidied up the same way.

### What front mode can and cannot know

**What counts as a reach.** Each time Quiet Hours leaves the foreground during the window and it was not a lock, a call or a restart: going home, switching apps, tapping a notification banner, Spotlight, closing Quiet Hours from the app switcher. Pulling down Control Center or Notification Center, Siri, or an incoming-call banner only make the app inactive, which is not counted. I believe opening the app switcher without picking another app keeps Quiet Hours inactive, not backgrounded, so it is not counted; untested.

**Lock versus app switch: the method.** There is no public "the phone locked" event (Apple DTS: no API for lock and unlock, [thread 769072](https://developer.apple.com/forums/thread/769072)). The private Darwin notification `com.apple.springboard.lockcomplete` would say so instantly but is off limits. The most reliable public signal is data protection:
- `UIApplication.protectedDataWillBecomeUnavailableNotification` "lets your app know that the device is about to be locked" ([docs](https://developer.apple.com/documentation/uikit/uiapplicationdelegate/applicationprotecteddatawillbecomeunavailable(_:))), and `isProtectedDataAvailable` is false while locked ([docs](https://developer.apple.com/documentation/uikit/uiapplication/isprotecteddataavailable)). Data protection is on whenever a passcode is set ([Encrypting your app's files](https://developer.apple.com/documentation/uikit/encrypting-your-app-s-files)).
- Apple Platform Security: the Complete Protection class key goes 10 s after locking, if Require Password is Immediately ([Data Protection classes](https://support.apple.com/guide/security/secb010e978a/web)). With Face ID or Touch ID on, Require Passcode cannot be anything but Immediately ([Apple Support 119586](https://support.apple.com/en-us/119586)).
- So a lock shows up about 10 s after it happens. The app holds a background task (Apple doesn't promise a length; DTS says expect about 30 s, [thread 85066](https://developer.apple.com/forums/thread/85066)) and waits 15 s for it.

**How sure.**
- **Face ID or Touch ID on:** expected reliable, not yet tested. DTS describes these notifications as about data protection rather than screen lock, and says iOS delays data protection for a while ([thread 70079](https://developer.apple.com/forums/thread/70079), [thread 744170](https://developer.apple.com/forums/thread/744170)). The 10 s timing is Apple's; delivery to a background app within 15 s is what the device test checks.
- **Passcode without Face ID or Touch ID:** uncertain. Require Passcode may be set to a delay, and then locks count as stepping out.
- **No passcode:** no signal at all. Every lock counts as stepping out, and becomes a leave after 2 minutes. The stepped-out notification also lights up the locked phone.
- The engine checks this without prompting (`LAContext.canEvaluatePolicy`) and puts a sentence in `state.setupWarning` for the last two cases. It cannot see the "Use Face ID for iPhone Unlock" switch itself. Whether to refuse to run front mode without Face ID or Touch ID is a product call.
- **Known miscount:** a lock and unlock inside about 10 s (before the signal) looks exactly like a quick trip to another app. It counts as one reach. Not counted as leaving.
- **Known miss:** if iOS gives less background time than 15 s, the app decides later from stored facts and treats the absence as `out`. A lock in that case is counted as a reach.

**Pocketing.** Either Quiet Hours stays in front with the screen on (in), or the phone auto-locks, which is a lock.

**Calls.** `CXCallObserver` works for any app without entitlements and sees incoming calls before they connect ([docs](https://developer.apple.com/documentation/callkit/cxcallobserver)), but only while the app is running: "It is specifically NOT expected to work while apps are suspended" (Apple DTS, [thread 849682](https://developer.apple.com/forums/thread/849682), Oct 2026). So:
- A call ringing or connected when Quiet Hours leaves the front, or that starts in the next 15 s, excuses the absence. Leaving Quiet Hours for another app while on a call is also excused.
- A call that starts after someone has already stepped out is not seen; the grace period keeps running.
- Answering from the incoming-call banner keeps Quiet Hours in front, so nothing happens at all.
- FaceTime and VoIP apps that use CallKit are seen too.

**After a lock, call or restart, nothing is seen until Quiet Hours is in front again.** The app is suspended. The usual paths come back to it: unlocking returns to the last app, and I expect ending a full-screen call to return there as well (untested). The gap: unlocking straight into another app (tapping a notification on the lock screen, the camera, a lock-screen widget) is never seen, and the person stays "in" until they next open Quiet Hours or the window ends. The log records how long each excused absence lasted when they come back.

**Closing Quiet Hours (force-quit).** Closing it from the app switcher means it is no longer in front, so it counts as stepping out. Apple sends no reliable notice of a force-quit ("generally not called when the user quits the app", [applicationWillTerminate](https://developer.apple.com/documentation/uikit/uiapplicationdelegate/applicationwillterminate(_:))). What the engine does:
- If the app had already gone to the background, the absence and the queued notification already exist, and the next launch settles it as `out`.
- If the notice comes while Quiet Hours was still in front, it records an absence and queues the notification.
- If the app dies in front with no notice (also a crash), the next launch sees the stale heartbeat (written every 5 s while in front) and logs a "stop", not counted.

**Restart mid-window.**
- If the phone restarted during an absence (boot time from `sysctl kern.boottime` later than the absence start), the absence is `restart`: not counted, never a leave.
- If it restarted while Quiet Hours was in front (power-off slider), the next launch logs it.
- After a restart iOS opens on the home screen, not Quiet Hours, so the person is "in" but unobserved until they open it.
- I chose not to count restarts because there is no evidence the person used the phone; a dead battery looks the same. Counting it as leaving would make a leave out of nothing. The record shows the count (`front.restarts`).
- A notification queued before the restart may still be delivered after it.

**What is reported.** Same fields as Screen Time mode: `reachCount` (times stepped out), `leftAt`, `appliedAt` (in since). `stayPresses` is always 0. The server needs no change, but it must accept a `leftAt` in the past, as in Screen Time mode.

**Product questions front mode raises.**
- Someone who never opens Quiet Hours during the window is never "in". Should the server count them as in at `startsAt`?
- The notification uses the default interruption level. A Focus may hold it. Time-sensitive delivery needs an entitlement I have not tried on the free team.

### Front mode values

| Value | Setting | Why |
|---|---|---|
| Grace period | 120 s (`frontGracePeriod`) | Long enough to answer a text and come back, short enough to mean something. |
| Lock detection | 15 s (`frontLockDetectionWindow`) | The lock signal arrives about 10 s after a lock; 5 s of margin, well inside about 30 s of background time. |
| Stepped-out notification | 17 s after leaving (`frontNotificationDelay`) | 2 s after the decision, so a lock seen at the decision still cancels it. It cannot fire at the moment of leaving: then a lock and an app switch look the same, and it would light up every phone that had just been locked. |
| Heartbeat | 5 s (`frontHeartbeatInterval`) | Dates the last moment the app was seen in front, for a crash, force-quit or power-off with no notice. |
| Test window | 5 min (`frontTestWindowLength`) | Longer than the grace period, so a leave can be tested. |

## Contract items the platform cannot do as written

- **"Each time the shield is met counts as one reach."** Screen Time mode: no exact signal exists; the closest approximation is above. This also strains "every number shown is a real count from stored rows": the rows will be real, but the reach rows are an approximation of the event. Front mode: a reach is a trip out of Quiet Hours, which is countable, with the lock and call limits above.
- **"Leaving ... is reported to the server."** Yes, but not reliably immediately. Screen Time: limit 7. Front mode: a grace-period leave is written the next time the app runs. The server should accept a leave with a `leftAt` in the past.
- **Shield subtitle "includes the current count."** Only the count as of the app's last write (limit 5). Front mode has no shield.
- **"The lock must start and stop on time even if the app is not open."** Screen Time: yes, in the sense of limit 3. Front mode: no. It starts when the person opens Quiet Hours.
- **"Calls and the user's chosen essentials stay open."** Screen Time: see "Total lock". Front mode: calls are excused; there is no notion of essentials, since any other app is out.
- **"Stayed: share of people who ... never left."** Can be inflated by people who turn off Screen Time access instead of pressing Leave (limit 8), and in front mode by the unobserved gaps above.
- **"The lock uses Apple's Screen Time frameworks."** Not in front mode, by design.

## What the future UI calls

All of it is on `QuietHoursEngine.shared` (main actor, `@Observable`). The same calls compile and work in both modes.

| Call | Purpose |
|---|---|
| `state` | Everything to display. Read it, don't cache it. See `QuietState` in `App/Engine/QuietHoursEngine.swift`. |
| `state.mode` | `screenTime` or `front`: which lock is compiled in. |
| `requestAuthorization()` | Screen Time access (Face ID prompt). Front mode: returns at once. Then read `state.isAuthorized`. |
| `requestNotificationPermission()` | Pre-start notification; in front mode also the stepped-out notification. |
| `state.usesAppPicker`, `.quietHoursAppPicker(isPresented:)` | Screen Time mode: put the modifier on any view and set the binding to show Apple's picker; it saves the picks. Front mode: `usesAppPicker` is false and the modifier does nothing. |
| `state.lockScope`, `setLockScope(_:)` | Screen Time mode: `.allExcept` (default) or `.selected`. Changing it clears the picks. Nil / ignored in front mode. |
| `state.hasSelection`, `state.isReadyToSchedule`, `state.setupWarning` | Whether a window can be scheduled now, and a sentence about anything that will make the lock misjudge. |
| `scheduleWindow(id:start:end:)` | Schedule this week's window. Pass the server's week id as `id`. Throws `QuietEngineError`. Replaces any window already scheduled. |
| `cancelWindow()` | For "skip": removes the lock, notifications and Live Activity. |
| `leaveEarly()` | Leave from inside the app. Returns false if no window is in progress. |
| `state.phase` | `none`, `scheduled`, `due` (in the window, lock not on yet / Quiet Hours not opened yet), `active`, `steppedOut` (front mode), `left`, `ended`. Also `isScheduled`, `isActive` (includes `due` and `steppedOut`), `hasLeft`. |
| `state.backBy` | Front mode: when the person must be back to stay in. |
| `state.leftAt`, `state.window?.id`, `state.reachCount`, `state.stayPresses` | What to report to the server. |
| `setPeopleCount(_:)` | Screen Time mode: the live count for the shield subtitle. |
| `setLeaveOpensApp(_:)` | Screen Time mode, iOS 26.5+: make Leave open the app. |
| `didBecomeActive()` | Call when the scene becomes active. |
| `refresh()` | Re-read shared state. Cheap; the debug screen calls it every second. |

Screen Time builds also have `selection`, `updateSelection(_:)` and `pickerStartingSelection()` for a UI that drives Apple's picker itself. The shield's words are in `Shared/ScreenTime/ShieldCopy.swift`; the front-mode notification's in `App/Engine/Front/SteppedOutNotification.swift`; the Live Activity's look in `Extensions/Widgets/QuietHoursWidgets.swift`. All are placeholders for the design work.

## Choices I made that you may want to revisit

- **Leave response.** After clearing the lock, the shield action answers `.defer`, which per [the docs](https://developer.apple.com/documentation/managedsettings/shieldactionresponse/defer) makes the shield redraw. With the lock gone, the app underneath should become usable. The alternative is `.close`. The device test checks this.
- **Merge interval of 3 seconds** for reaches (`QuietConstants.reachMergeInterval`).
- **Notification 5 minutes before** the start (`QuietConstants.preStartLead`).
- **Ended Live Activity dismissal.** It stays 10 minutes after a natural end, and is removed immediately after leaving or cancelling.
- **App as backstop.** If the app is open inside the window and the monitor has not applied the lock, the app applies it. The log records who did (`appliedBy`).
- **Debug test window start.** It starts on the next whole minute at least 60 seconds away, so it begins 60 to 120 seconds after the tap.
- **Total lock is the default** (see "Total lock").
- **Front mode:** quick returns count as reaches; restarts and stops are not counted; calls excuse the whole absence they start; the front-mode values above.
- **One bundle id for both builds.** Installing the full build later replaces the front build and keeps its stored data. A window scheduled by one build is dropped when the other build launches, since it cannot enforce it.

## Build record

No iOS Simulator runtime is installed on this Mac (only visionOS 27.2), and no phone was connected, so nothing was launched. The builds prove compilation and signing only.

**1. Generate.** `cd ios && xcodegen generate` (XcodeGen 2.46.0). Result: `Created project at /Users/hartleyscales/quiet-hours/ios/QuietHours.xcodeproj`. Schemes: `QuietHours`, `QuietHoursFront`.

**2. Both variants, simulator and device, signing off.** All four succeeded with 0 Swift warnings. Device builds show one project warning, "All interface orientations must be supported unless the app requires full screen", from the portrait-only Info.plist setting the previous build already had.

```
xcodebuild -project QuietHours.xcodeproj -scheme QuietHours      -destination 'generic/platform=iOS Simulator' CODE_SIGNING_ALLOWED=NO clean build
xcodebuild -project QuietHours.xcodeproj -scheme QuietHours      -destination 'generic/platform=iOS'           CODE_SIGNING_ALLOWED=NO clean build
xcodebuild -project QuietHours.xcodeproj -scheme QuietHoursFront -destination 'generic/platform=iOS Simulator' CODE_SIGNING_ALLOWED=NO clean build
xcodebuild -project QuietHours.xcodeproj -scheme QuietHoursFront -destination 'generic/platform=iOS'           CODE_SIGNING_ALLOWED=NO clean build
...
** BUILD SUCCEEDED **   (each)
```

What is in each device product: `QuietHours.app` embeds Monitor, ShieldAction, ShieldConfiguration and Widgets, links FamilyControls, ManagedSettings, DeviceActivity, ActivityKit, and carries `com.apple.developer.family-controls`. `QuietHoursFront.app` embeds only Widgets, links ActivityKit, CallKit and LocalAuthentication, and its entitlements hold only the App Group.

**3. Front variant, device, automatic signing (one attempt).** Succeeded.

```
xcodebuild -project QuietHours.xcodeproj -scheme QuietHoursFront -destination 'generic/platform=iOS' -allowProvisioningUpdates build
    Provisioning Profile: "iOS Team Provisioning Profile: com.hms-web-development.QuietHours"
    Provisioning Profile: "iOS Team Provisioning Profile: com.hms-web-development.QuietHours.Widgets"
    Signing Identity:     "Apple Development: <Apple ID> (7TZFLAC2B4)"
** BUILD SUCCEEDED **
```

Xcode created one new development profile on the Personal Team, for `com.hms-web-development.QuietHours` (App Groups: `group.com.hms-web-development.QuietHours`; 1 device; expires 2026-11-21, free-team profiles last 7 days). It reused the existing Widgets profile. `codesign --verify --deep --strict` passes; the app's signed entitlements are the App Group, team and application id only. Nothing else on the account or the Mac was changed. This build was made before a final round of code fixes; those changed code only, not bundle ids, entitlements or capabilities, and the signing-off builds in step 2 are of the final code.

**Earlier (Screen Time scheme, before front mode).** Automatic signing failed, as expected on a free team: "Personal development teams ... do not support the Family Controls (Development) capability." That attempt registered the App Group and a development profile for `com.hms-web-development.QuietHours.Widgets` on the Personal Team. It still fails the same way; the Screen Time scheme needs a paid team.
