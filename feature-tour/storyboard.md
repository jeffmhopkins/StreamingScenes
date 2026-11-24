# Feature tour: storyboard

Generated from `feature-tour.json` by `make_storyboard.py`, so it says what the project holds.
Every picture is drawn live by JStream from the project: screenshots of the app are image
sources, and every move is a keyframe loaded by the show. Nothing is a pre-rendered video.

Show **Feature tour**: 16 clips, 5:34 without pauses, 16 bookmarks, 2 loops, 39 keyframe markers, planned at 20:00.

Design: the app's own palette, IBM Plex, frameless windows with one shadow recipe, a spotlight and a
menu-style chip per callout, glide easing on every camera move ([design-language.md](design-language.md)).

## 0:00 · Pre-show

*scene `s_hold`, 20 s; bookmark plays through*

On screen: “JSTREAM FEATURE TOUR” / “We start in a moment” / “A short tour of JStream, a live streaming studio”

- 0:00–0:20 loop **Pre-show**, leaves at once

> **Note for the presenter**
> *Holding slate. It loops until you press Continue.*
> 
> Hi everyone, we'll start in just a moment.
> 
> *Check your sound and the stream health, then press Continue.*

## 0:20 · Welcome

*scene `s_title`, 12 s; in with Slow fade; bookmark plays through*

- 0:21 **Push** (Drift)
- 0:26 overlay v3: FEATURE TOUR / JStream / A live streaming studio
- 0:20 cue on s1: `timeline.play` timeline_id=title_build
- 0:20 audio: desktop audio at -8 dB for 12 s

> **Note for the presenter**
> This is JStream. It's a live streaming and compositing studio, written from scratch in Rust. It does the job of a studio like OBS: scenes, sources, mixing, streaming and recording.
> 
> It's pre-release, and the show features you're about to see arrive in the next pre-release.
> 
> And everything you're watching right now is a JStream project, run by a JStream show. None of it is a video.

## 0:32 · The studio

*scene `s_studio`, 29 s; in with Fade; bookmark pauses here*

- 0:36 **Scenes** (Glide): Scenes and sources — A scene stacks sources: cameras, screen and window capture, media, browser pages, text, timers and audio visualisers.
- 0:41 **Canvas** (Glide): Composited on the GPU — Each item can be cropped, turned in 3D, blended and given effects, live.
- 0:47 **Inspector** (Glide): Edits undo per client — Your undo never takes back a change made by another client: a browser, the command line or an agent.
- 0:52 **Outputs** (Glide): Outputs apart from scenes — Outputs take video mixes and audio buses, so a stream and a recording can carry different pictures and sound.
- 0:58 back to the establishing shot (Glide)
- 0:32 overlay v2: 01 / THE STUDIO / One app, every source
- 0:32 overlay v4: RENDERED IN JSTREAM

> **Note for the presenter**
> Here's the studio. A scene is a stack of sources: cameras, screen and window capture, media, browser pages, text, timers and audio visualisers. They're composited on the GPU, and every item can be cropped, turned in 3D, blended and given effects, live.
> 
> Edits undo per client. My undo never takes back a change somebody else made, from a browser, the command line or an agent.
> 
> And outputs take video mixes and audio buses, not scenes, so the stream and the recording can carry different pictures and sound.

## 1:01 · What you make

*scene `s_make`, 12 s; in with Fade; bookmark plays through*

On screen: “MISSION FEED” / “LIVE” / “CAM 1  ·  MAIN FEED” / “CAM 2  ·  LAB CAM” / “CAM 3  ·  SKY CAM” / “Image, text, shape, timer and scene sources. No browser source.”

- 1:01 overlay v2: 02 / WHAT YOU MAKE / A broadcast, built in

> **Note for the presenter**
> Here's the kind of scene you can make. This is a live JStream scene, not a picture of one.
> 
> Every piece is a built-in source: the feeds are images, cropped to 16:9 in the scene, the clock is a timer, and the lower third is a scene of its own, shown here as one layer.
> 
> *The footage is from Tears of Steel, the Blender Foundation's open film, under CC BY.*

## 1:13 · Keyframes

*scene `s_kf`, 25.5 s; in with Fade; bookmark pauses here*

On screen: “PROGRAM  ·  scene Mission feed” / “03” / “KEYFRAMES” / “Keyframes are layouts” / “One scene, several arrangements of its items. Loading one moves everything there.” / “Mission feed” / “the scene” / “Two-up” / “keyframe” / “Close-up” / “keyframe” / “Main feed” / “keyframe”

- 1:17 **Two-up** (Layout move): Two-up — A keyframe overrides each item's place, size, crop, opacity, visibility and effects. Here the main feed steps aside.
- 1:22 **Close-up** (Layout move): Close-up — A Move glides every item at once on one easing curve; each item can have its own delay and duration.
- 1:28 **Main feed** (Layout move): Main feed — The show's keyframe track loads these. A sequence cue, a hotkey or a MIDI pad can too.
- 1:33 back to the establishing shot (Layout move)

> **Note for the presenter**
> Now the part I'm most excited about: keyframes.
> 
> This is one scene, called Mission feed. A keyframe is a saved arrangement of that same scene. It can change where each item sits, its size, crop, opacity, whether it shows, and its effects.
> 
> Watch: Two-up. Close-up. Main feed. Every item glides at once, and each item can have its own delay. See the small picture land a beat late?
> 
> The show is loading these keyframes right now. A sequence, a hotkey or a MIDI pad can load them too.

## 1:38 · Motion

*scene `s_motion`, 16 s; in with Fade; bookmark plays through*

On screen: “04” / “MOTION” / “Items that move on their own” / “Motion modifiers move an item's position, scale, rotation, opacity or an effect setting, with no keyframes. Scene cameras take them too.” / “Wiggle” / “Seeded noise” / “Oscillate” / “A waveform” / “Drift” / “A steady rate” / “Impulse” / “Fired by a cue” / “Audio” / “Follows a sound level”

- 1:42 cue on s2: `item.trigger_motion` item_id=mo_i_impulse modifier_id=kick
- 1:46 cue on s2: `item.trigger_motion` item_id=mo_i_impulse modifier_id=kick
- 1:50 cue on s2: `item.trigger_motion` item_id=mo_i_impulse modifier_id=kick
- 1:38 audio: desktop audio at -12 dB for 16 s

> **Note for the presenter**
> Items can also move on their own, with no keyframes at all. These are motion modifiers.
> 
> Wiggle is seeded noise. Oscillate follows a waveform. Drift is a steady rate. Impulse fires on a cue, and the show is kicking it right now. Audio follows a sound level.
> 
> MIDI, live data and channels can drive them too. They work on position, scale, rotation, opacity and effect settings, and on scene cameras.

## 1:54 · Sequences & channels

*scene `s_seq`, 23.5 s; in with Fade; bookmark pauses here*

- 1:58 **Lanes** (Glide): Sequences move values over time — Lanes move channels along curves; cues fire actions such as showing an item or loading a keyframe.
- 2:04 **Triggers** (Glide): They can start themselves — A sequence can start or stop on a channel rising, a keyframe loading, a scene showing, or a key.
- 2:09 **Channel** (Glide): Channels: one number, many inputs — MIDI, live data, keys, cues or a lane can move a channel; positions, cameras, effects and live settings follow it.
- 2:15 back to the establishing shot (Glide)
- 1:54 overlay v2: 05 / SEQUENCES / Sequences and channels

> **Note for the presenter**
> Sequences move values over time.
> 
> A channel is one number. MIDI, live data, keys, cues or a lane on a sequence can move it, and positions, cameras, effects and live settings can follow it.
> 
> A sequence has lanes, which are curves on channels, and cues, which are actions on a clock. It can even start itself: when a channel rises, a keyframe loads, a scene shows, or you press a key.

## 2:18 · Shows

*scene `s_show`, 40 s; in with Sweep sting; bookmark pauses here; arrives with Sweep sting*

- 2:22 **Tracks** (Glide): A show is the whole run order — Program, overlay, keyframe, sequence and audio tracks on one timeline, saved with the project.
- 2:27 **Loop** (Glide): Loops hold until you're ready — A loop repeats a span, like a waiting room, until you press Continue.
- 2:33 **Bookmarks** (Glide): Bookmarks pause or play through — Jump to any bookmark and the studio is set as playing there would have left it.
- 2:38 **Notes** (Glide): Notes for whoever runs it — Each bookmark has a name, a pausing switch, an arrival transition, its own Go to key, and a note like this tour's talking points.
- 2:44 **Continue** (Glide): One button runs it — Continue is an action like any other, so a key, a MIDI pad or a click can press it.
- 2:49 **Run view** (Glide): A view for show time — Now and next, every bookmark as a button, and clocks against the planned length.
- 2:55 back to the establishing shot (Glide)
- 2:18 overlay v2: 06 / SHOWS / Run the whole show

> **Note for the presenter**
> And this is what's running the whole presentation: a show.
> 
> One timeline, with program, overlay, keyframe, sequence and audio tracks, saved with the project. Bookmarks pause or play through. Loops hold, like a waiting room, until I press Continue.
> 
> I can jump to any bookmark, and the studio is set the way playing there would have left it.
> 
> And the notes I'm reading right now? They're this bookmark's note.

## 2:58 · 3D cockpit

*scene `s_3d`, 29 s; in with Slow fade; bookmark pauses here*

- 3:02 **Monitor** (Glide): A live picture on a 3D monitor — Any 2D scene, such as a camera feed, plays on the model's monitor through the model's texture setting.
- 3:07 **Bitwig** (Glide): Bitwig, live, over JTunnel — The cockpit's screens are browser-source pages drawing Bitwig's live data. Here the session is simulated.
- 3:13 **Fields** (Glide): What Bitwig sends — Clock and tempo, transport, the clip grid and scenes, track meters, notes, mixer, device, clip and markers.
- 3:18 **Mapped** (Glide): Mapped onto the scene — Data modifiers map a field onto an item's position, opacity or settings: here the meters drive the cabin lights and glow.
- 3:24 back to the establishing shot (Glide)
- 2:58 overlay v2: 07 / 3D SCENES / A glTF cockpit, rendered in JStream

> **Note for the presenter**
> Scenes can be 3D. It's opt in, per scene: give a scene a camera and its items get depth. Most scenes stay 2D.
> 
> Here's one example, a glTF cockpit rendered in JStream. Any 2D scene, like a camera feed, can play on the model's monitor.
> 
> The screens show Bitwig, live, over JTunnel. Here the session is simulated. Bitwig sends the clock and tempo, transport, clip grid and scenes, track meters, notes, mixer, device, clip and markers. Pages draw it, and data modifiers map any of it onto the scene. Here the meters drive the cabin lights.

## 3:27 · DAW & web pages

*scene `s_link`, 16 s; in with Fade; bookmark pauses here*

On screen: “08” / “CONNECTED” / “Your DAW and your web pages, in the loop”

- 3:27 cue on s1: `timeline.play` timeline_id=link_build

> **Note for the presenter**
> JStream connects to your music setup.
> 
> JTunnel is a CLAP plugin. It sends a track's audio and MIDI over the local network, and JStream takes the audio as a source and the MIDI as bindings. You accept each sender first.
> 
> In Bitwig, JTunnel also sends the clip grid, transport and device. And a browser source's page can read JStream's clock, scenes, levels, tempo, MIDI and DAW data, each behind its own switch.

## 3:43 · Keys & MIDI

*scene `s_keys`, 18 s; in with Fade; bookmark pauses here, continues by itself after 12 s*

- 3:47 **Binding** (Glide): One binding system — Hotkeys, MIDI controllers and tempo sync share it, and a key or pad can play a sequence of cues.
- 3:52 **Explained** (Glide): Bindings run ordinary actions — A key or a pad runs the same actions the buttons do: switch scenes, load keyframes, play sequences, go live.
- 3:58 back to the establishing shot (Glide)
- 3:43 overlay v2: 09 / CONTROL / Keys, pads and MIDI

> **Note for the presenter**
> Control works one way for everything. Hotkeys, MIDI controllers and tempo sync share one binding system.
> 
> A key or a pad runs the same actions the buttons do: switch scenes, load keyframes, play sequences, go live.
> 
> *This bookmark continues by itself after 12 seconds.*

## 4:01 · Effects

*scene `s_fx`, 18 s; in with Fade; bookmark plays through*

- 4:05 **Item effects** (Glide): Effects on one item — Rounded corners and a drop shadow on this item only, applied live, in order.
- 4:10 **Result** (Glide): Shader packs — Beyond the built-in filters, shader sources and filters can be written as WGSL effect packs.
- 4:16 back to the establishing shot (Glide)
- 4:01 overlay v2: 10 / EFFECTS / Filters and effects

> **Note for the presenter**
> Effects, quickly. Built-in filters work on sources, items, scenes and outputs. And for anything beyond those, you can write shader sources and filters as WGSL effect packs.

## 4:19 · Plugins

*scene `s_plug`, 12.5 s; in with Fade; bookmark pauses here*

- 4:23 **Access** (Glide): Plugins ask, you grant — Automation plugins run sandboxed and get only the access their manifest asks for and you grant. An update that asks for more stays off until you grant it again.
- 4:28 back to the establishing shot (Glide)
- 4:19 overlay v2: 11 / EXTEND / Plugins, with permission

> **Note for the presenter**
> Automation plugins run sandboxed. A plugin only gets the access its manifest asks for and you grant. And if an update asks for more, it stays off until you grant it again.

## 4:31 · Cameras & going live

*scene `s_cam`, 29 s; in with Fade; bookmark pauses here*

- 4:35 **Drive** (Glide): Drive real cameras — Drive PTZ cameras from the panel, recall shots from a key, and map pan, tilt, zoom and focus to MIDI.
- 4:41 **Presets** (Glide): Shots belong to scenes — A scene can carry each camera's shot, so switching the scene aims the cameras.
- 4:46 **Health** (Glide): Health you can read — Bitrate, dropped frames and a plain verdict on how the stream is doing.
- 4:52 **Encoders** (Glide): Settings per output — Each stream or recording has its own encoder settings, video mix and audio bus.
- 4:57 back to the establishing shot (Glide)
- 4:31 overlay v2: 12 / CAMERAS & GOING LIVE / PTZ cameras, streaming, recording

> **Note for the presenter**
> PTZ cameras: drive them from the panel, recall shots from a key, and map pan, tilt, zoom and focus to MIDI. A scene can carry each camera's shot, so switching the scene aims the cameras.
> 
> Going live: RTMP or RTMPS to YouTube or any service with a stream key, a recording at the same time, and a virtual camera on Windows and Linux. Each stream or recording gets its own encoder, mix and bus.
> 
> *The stats panel is from a test engine, so its numbers are illustrative.*

## 5:00 · Under the hood

*scene `s_built`, 14 s; in with Fade; bookmark pauses here*

On screen: “13” / “UNDER THE HOOD” / “Written from scratch, around one idea.”

- 5:00 cue on s1: `timeline.play` timeline_id=built_build
- 5:14 cue on s2: `channel.set_value` channel_id=glow fade_ms=400 value=0.0

> **Note for the presenter**
> Under the hood.
> 
> Everything is an API. The app is just one client of the protocol, so a script, the command line, or an AI agent over MCP can drive almost anything a person can.
> 
> It's Rust, and the real-time audio thread never allocates, locks or blocks. Tests enforce that. It runs headless too. And it's open source, MIT or Apache-2.0.

## 5:14 · Thanks

*scene `s_thanks`, 20 s; in with Slow fade; bookmark pauses here*

On screen: “JStream” / “Thank you.” / “github.com/jeffmhopkins/JStream”

- 5:14 cue on s1: `timeline.play` timeline_id=outro_glow
- 5:14 audio: desktop audio at -10 dB for 20 s
- 5:18–5:30 loop **Outro**, leaves after finishing its pass

> **Note for the presenter**
> Thank you! Happy to take questions.
> 
> *The Outro loop finishes its pass when you press Continue. Then the show goes back to the Pre-show, ready to run again.*

## End

The show ends by going to the bookmark `preshow`, so it is ready to run again.

## The second show: Lightning tour (no pauses)

`s_title` (10 s), then `s_kf` (25.5 s), then `s_3d` (29 s), then `s_thanks` (10 s). It loops, with the Next monitor live: one project, several shows, shared scenes.
