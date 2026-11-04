//! Scratch: the camera track for the follow-cursor demo, from the real follow camera
//! (not committed). Writes `cameras.jsonl` (one SceneCamera a frame) and `cursor.jsonl`.
use std::io::Write;

use jstream_media::{MediaTime, Timebase};
use jstream_protocol::{Canvas, CameraFollow, Finite32, ItemId, SceneCamera, SceneId};

use super::{Cameras, FollowBox, Tuning};

fn min_jerk(t: f32) -> f32 {
    let t = t.clamp(0.0, 1.0);
    t * t * t * (t * (t * 6.0 - 15.0) + 10.0)
}

enum Seg {
    Dwell(f32),
    Move(f32, (f32, f32)),
    Circle(f32, (f32, f32), f32, f32),
}

/// A scripted mouse over the 1440 × 900 UI capture.
fn cursor_path(fps: f32) -> Vec<(f32, f32)> {
    let script = [
        Seg::Dwell(1.2),
        Seg::Move(0.9, (1190.0, 210.0)), // the inspector's X field
        Seg::Dwell(1.0),
        Seg::Move(0.5, (1190.0, 266.0)), // W, a small hop inside the dead zone
        Seg::Dwell(1.2),
        Seg::Move(0.8, (1020.0, 476.0)), // to the Monitors box's edge
        Seg::Circle(5.0, (900.0, 476.0), 120.0, 2.0),
        Seg::Dwell(0.6),
        Seg::Move(0.35, (95.0, 148.0)), // a quick flick to the scene list
        Seg::Dwell(1.3),
        Seg::Move(3.0, (95.0, 560.0)), // slowly down the sources
        Seg::Dwell(0.8),
        Seg::Move(1.0, (440.0, 806.0)), // the mixer
        Seg::Dwell(1.5),
        Seg::Move(0.6, (1385.0, 24.0)), // Go Live, at the capture's corner
        Seg::Dwell(1.5),
        Seg::Circle(3.0, (540.0, 218.0), 60.0, 1.0), // round the title on the canvas
        Seg::Move(1.0, (700.0, 380.0)),
        Seg::Dwell(2.0),
    ];
    let mut out = Vec::new();
    let mut at = (700.0_f32, 380.0_f32);
    let mut n = 0usize;
    let tremor = |n: usize| {
        let k = n as f32;
        (0.8 * (k * 0.71).sin() + 0.5 * (k * 1.93).sin(), 0.7 * (k * 0.83).cos() + 0.4 * (k * 2.31).sin())
    };
    for seg in script {
        match seg {
            Seg::Dwell(d) => {
                for _ in 0..(d * fps) as usize {
                    let j = tremor(n);
                    out.push((at.0 + j.0, at.1 + j.1));
                    n += 1;
                }
            }
            Seg::Move(d, to) => {
                let from = at;
                let frames = (d * fps).max(1.0) as usize;
                let (dx, dy) = (to.0 - from.0, to.1 - from.1);
                let len = (dx * dx + dy * dy).sqrt().max(1.0);
                let bow = 0.08 * len;
                for i in 1..=frames {
                    let s = min_jerk(i as f32 / frames as f32);
                    let side = bow * (std::f32::consts::PI * s).sin();
                    out.push((from.0 + dx * s - dy / len * side, from.1 + dy * s + dx / len * side));
                    n += 1;
                }
                at = to;
            }
            Seg::Circle(d, c, r, turns) => {
                let a0 = (at.1 - c.1).atan2(at.0 - c.0);
                let frames = (d * fps) as usize;
                for i in 1..=frames {
                    let s = i as f32 / frames as f32;
                    let a = a0 + std::f32::consts::TAU * turns * min_jerk(s);
                    let rr = r * (1.0 + 0.06 * (a * 3.0).sin());
                    out.push((c.0 + rr * a.cos(), c.1 + rr * a.sin()));
                    n += 1;
                }
                at = *out.last().expect("a point");
            }
        }
    }
    out
}

/// Zoom steps (`scene.zoom_camera`, from a hotkey) at given seconds.
const ZOOM: [(f32, i64); 9] = [
    (2.4, 1), (2.55, 1), (2.7, 1),
    (12.0, -1), (12.1, -1), (12.2, -1), (12.3, -1),
    (21.0, 2),
    (27.0, -3),
];

#[test]
#[ignore]
fn follow_track() {
    let dir = std::env::var("REEL").expect("REEL dir");
    let fps = 30.0_f32;
    let canvas = Canvas { width: 1920, height: 1080 };
    let screen = FollowBox { center: [960.0, 540.0], size: [1440.0, 900.0], depth: 0.0 };
    let base = SceneCamera {
        fov_deg: Finite32::new(40.0).expect("finite"),
        blur_px: Finite32::new(44.0).expect("finite"),
        focus_px: Finite32::new(800.0),
        ..SceneCamera::framing(canvas)
    };
    let follow = CameraFollow { zoom: Finite32::new(1.4).expect("finite"), ..CameraFollow::of(ItemId::new("screen")) };
    let family = SceneId::new("demo");
    let mut cameras = Cameras::default();
    let path = cursor_path(fps);
    let mut zooms = 0_i64;
    let mut z = 0;
    let mut cams = std::fs::File::create(format!("{dir}/cameras.jsonl")).expect("cameras");
    let mut cur = std::fs::File::create(format!("{dir}/cursor.jsonl")).expect("cursor");
    for (i, &c) in path.iter().enumerate() {
        let now = i as f32 / fps;
        while z < ZOOM.len() && ZOOM[z].0 <= now {
            zooms += ZOOM[z].1;
            z += 1;
        }
        let at = MediaTime::new((now * 1000.0).round() as i64, Timebase::new(1, 1000).expect("tb"));
        let camera = cameras.follow(&family, &follow, base, canvas, screen, Some(c), (at, zooms));
        writeln!(cams, "{}", serde_json::to_string(&camera).expect("json")).expect("w");
        writeln!(cur, "[{:.2},{:.2}]", c.0, c.1).expect("w");
        let (u, v) = Tuning::new(&follow, base, canvas, screen).seen(camera, c);
        if u.abs() > 1.0 || v.abs() > 1.0 {
            let _ = writeln!(std::io::stderr(), "off {i} t {now:.2} cursor {c:?} uv {u:.2} {v:.2}");
        }
    }
    let _ = writeln!(std::io::stderr(), "frames {}", path.len());
}
