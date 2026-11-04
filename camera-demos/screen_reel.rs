//! Scratch: a close-up of a screen, the camera gliding between angles (not committed).
use std::io::Write;
use jstream_media::FrameSize;
use jstream_protocol::{Canvas, Finite32, FitMode, ItemGeometry, SceneCamera, Size, Vec2, Vec3};
use super::{item, open};
use crate::{Color, Crop, Placement, Scene};

const W: u32 = 1920;
const H: u32 = 1080;

fn f(v: f32) -> Finite32 { Finite32::new(v).expect("finite") }

/// One held angle: the screen point looked at (in 1440 × 900 UI pixels), the view's yaw
/// and pitch off the screen's normal, roll, and distance.
#[derive(Clone, Copy)]
struct Shot { aim: (f32, f32), yaw: f32, pitch: f32, roll: f32, dist: f32 }

fn smoother(t: f32) -> f32 { let t = t.clamp(0.0, 1.0); t * t * t * (t * (t * 6.0 - 15.0) + 10.0) }

fn lerp(a: Shot, b: Shot, t: f32) -> Shot {
    let l = |x: f32, y: f32| x + (y - x) * t;
    Shot { aim: (l(a.aim.0, b.aim.0), l(a.aim.1, b.aim.1)), yaw: l(a.yaw, b.yaw), pitch: l(a.pitch, b.pitch), roll: l(a.roll, b.roll), dist: l(a.dist, b.dist) }
}

#[test]
#[ignore]
fn screen_reel() {
    let dir = std::env::var("REEL").expect("REEL dir");
    let dry = std::env::var_os("DRY").is_some();
    let canvas = Canvas { width: W, height: H };
    // The screen, flat at depth 0, centred on the canvas: 1440 × 900 scene pixels.
    let screen = ItemGeometry {
        fit_mode: FitMode::Stretch,
        ..ItemGeometry::try_new(Vec2::new(960.0, 540.0).expect("f"), Size::try_new(1440.0, 900.0).expect("p")).expect("g")
    };
    let world = |aim: (f32, f32)| [aim.0 - 720.0 + 960.0, aim.1 - 450.0 + 540.0, 0.0];
    let shots = [
        Shot { aim: (900.0, 470.0), yaw: -32.0, pitch: -12.0, roll: 5.0, dist: 305.0 },
        Shot { aim: (1270.0, 250.0), yaw: 30.0, pitch: 10.0, roll: -6.0, dist: 325.0 },
        Shot { aim: (540.0, 230.0), yaw: 22.0, pitch: 16.0, roll: 3.0, dist: 425.0 },
        Shot { aim: (150.0, 190.0), yaw: -26.0, pitch: -14.0, roll: 4.0, dist: 385.0 },
        Shot { aim: (360.0, 790.0), yaw: 28.0, pitch: 14.0, roll: -4.0, dist: 335.0 },
        Shot { aim: (700.0, 380.0), yaw: -18.0, pitch: -10.0, roll: -2.0, dist: 475.0 },
    ];
    let (hold, glide) = (1.0_f32, 4.0_f32);
    let seg = hold + glide;
    let fps = 30.0;
    let total = seg * (shots.len() as f32 - 1.0) + hold;
    let frames = (total * fps) as usize;
    let base = SceneCamera::framing(canvas);
    let v = |p: [f32; 3]| Vec3 { x: f(p[0]), y: f(p[1]), z: f(p[2]) };
    let make = |s: Shot, dist: f32| -> SceneCamera {
        let target = world(s.aim);
        let (yaw, pitch) = (s.yaw.to_radians(), s.pitch.to_radians());
        let d = [yaw.sin() * pitch.cos(), pitch.sin(), yaw.cos() * pitch.cos()];
        let pos = [target[0] + d[0] * dist, target[1] + d[1] * dist, target[2] + d[2] * dist];
        SceneCamera {
            position: v(pos),
            target: v(target),
            fov_deg: f(40.0),
            roll_deg: f(s.roll),
            // The lens focuses on what the camera looks at.
            focus_px: Some(f(dist)),
            blur_px: f(48.0),
            ..base
        }
    };
    let covers = |cam: SceneCamera| -> bool {
        let Ok(view) = cam.view(canvas) else { return false };
        let m = 8.0;
        [(-m, -m), (W as f32 + m, -m), (W as f32 + m, H as f32 + m), (-m, H as f32 + m), (W as f32 * 0.5, -m), (W as f32 * 0.5, H as f32 + m), (-m, H as f32 * 0.5), (W as f32 + m, H as f32 * 0.5)]
            .iter()
            .all(|&(x, y)| match view.on_plane(jstream_protocol::CanvasPoint { x, y }, 0.0) {
                Some((px, py)) => (241.0..1679.0).contains(&px) && (91.0..989.0).contains(&py),
                None => false,
            })
    };
    let shot_at = |t: f32| -> Shot {
        let k = ((t / seg) as usize).min(shots.len() - 2);
        let local = ((t - k as f32 * seg - hold) / glide).clamp(0.0, 1.0);
        if t >= seg * (shots.len() as f32 - 1.0) { return shots[shots.len() - 1]; }
        lerp(shots[k], shots[k + 1], smoother(local))
    };
    // The farthest each frame's camera may be and still fill the frame with the screen,
    // capped by the shot's own distance, then smoothed so a pull-in glides too: a moving
    // minimum over ±1 s, then a moving mean over ±0.5 s, which never exceeds the limit.
    let limit: Vec<f32> = (0..frames)
        .map(|i| {
            let s = shot_at(i as f32 / fps);
            if covers(make(s, s.dist)) { return s.dist; }
            let (mut lo, mut hi) = (40.0_f32, s.dist);
            for _ in 0..30 { let mid = 0.5 * (lo + hi); if covers(make(s, mid)) { lo = mid } else { hi = mid } }
            lo
        })
        .collect();
    for k in (0..frames).step_by(30) { let _ = writeln!(std::io::stderr(), "t {:.0} limit {:.0} want {:.0} covers40 {}", k as f32 / fps, limit[k], shot_at(k as f32 / fps).dist, covers(make(shot_at(k as f32 / fps), 40.0))); }
    let window = |v: &[f32], i: usize, r: usize| (i.saturating_sub(r)..(i + r + 1).min(v.len())).map(|j| v[j]).collect::<Vec<_>>();
    let mins: Vec<f32> = (0..frames).map(|i| window(&limit, i, 30).into_iter().fold(f32::MAX, f32::min)).collect();
    let dist: Vec<f32> = (0..frames).map(|i| { let w = window(&mins, i, 15); w.iter().sum::<f32>() / w.len() as f32 }).collect();
    let camera = |i: usize| make(shot_at(i as f32 / fps), dist[i]);
    let bad = (0..frames).filter(|&i| !covers(camera(i))).count();
    for i in (0..frames).filter(|&i| !covers(camera(i))).take(5) { let _ = writeln!(std::io::stderr(), "bad {i} dist {} limit {} c40 {}", dist[i], limit[i], covers(make(shot_at(i as f32/fps), 40.0))); }
    let pulled = (0..frames).filter(|&i| dist[i] < shot_at(i as f32 / fps).dist - 1.0).count();
    let _ = writeln!(std::io::stderr(), "frames {frames}, pulled in on {pulled}, uncovered {bad}, dist {:.0}..{:.0}", dist.iter().cloned().fold(f32::MAX, f32::min), dist.iter().cloned().fold(0.0, f32::max));
    if dry { return; }
    let Some(mut opened) = open() else { panic!("no gpu") };
    let c = &mut opened.compositor;
    let bytes = std::fs::read(format!("{dir}/ui.rgba")).expect("tex");
    let ui = c.upload_rgba8(4320, 2700, &bytes).expect("upload");
    let mut out = std::fs::OpenOptions::new().write(true).open(format!("{dir}/frames.pipe")).expect("pipe");
    for i in 0..frames {
        let cam = camera(i);
        let items = [crate::Item { camera: Some(cam), ..item(&ui, Placement::Geometry(screen), Crop::NONE, 1.0) }];
        let scene = Scene { canvas: FrameSize::new(W, H).expect("nz"), background: Color::rgb(1.0, 0.0, 1.0), items: &items };
        let snap = c.render(&scene, true).expect("render").pixels().expect("rb").clone();
        out.write_all(snap.rgba()).expect("w");
    }
}
