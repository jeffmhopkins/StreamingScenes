//! Scratch: renders a depth-of-field demo reel (not committed).
use std::io::Write;
use jstream_media::FrameSize;
use jstream_protocol::{Finite32, FitMode, ItemGeometry, SceneCamera, Size, Vec2, Vec3, Canvas};
use super::{item, open};
use crate::{Color, Crop, Placement, Scene};

const W: u32 = 1280;
const H: u32 = 720;

fn geo(c: (f32, f32), s: (f32, f32), tilt: f32, turn: f32, depth: f32) -> ItemGeometry {
    let f = |v: f32| Finite32::new(v).expect("finite");
    ItemGeometry {
        fit_mode: FitMode::Stretch,
        tilt_deg: f(tilt),
        turn_deg: f(turn),
        depth_px: f(depth),
        ..ItemGeometry::try_new(Vec2::new(c.0, c.1).expect("f"), Size::try_new(s.0, s.1).expect("p")).expect("g")
    }
}

fn smooth(a: f32, b: f32, t: f32) -> f32 {
    let t = t.clamp(0.0, 1.0);
    let t = t * t * (3.0 - 2.0 * t);
    a + (b - a) * t
}

#[test]
#[ignore]
fn dof_reel() {
    let dir = std::env::var("REEL").expect("REEL dir");
    let Some(mut opened) = open() else { panic!("no gpu") };
    let load = |c: &mut crate::Compositor, n: &str, w: u32, h: u32| {
        let bytes = std::fs::read(format!("{dir}/{n}.rgba")).expect("tex");
        c.upload_rgba8(w, h, &bytes).expect("upload")
    };
    let c = &mut opened.compositor;
    let wall = load(c, "wall", 1024, 640);
    let floor = load(c, "floor", 512, 1024);
    let far = load(c, "far", 512, 640);
    let mid = load(c, "mid", 512, 640);
    let near = load(c, "near", 512, 640);
    let base = SceneCamera::framing(Canvas { width: W, height: H });
    let cam_z = base.position.z.get();
    // depth -> distance along the view
    let d = |depth: f32| cam_z - depth;
    let (dn, dm, df) = (d(380.0), d(0.0), d(-550.0));
    let fps = 30.0;
    let frames = 330;
    let mut captions = std::fs::File::create(format!("{dir}/captions.txt")).expect("c");
    for i in 0..frames {
        let t = i as f32 / fps;
        // (focus, blur, dof on)
        let (focus, blur, on) = if t < 1.5 {
            (dm, 0.0, false)
        } else if t < 3.0 {
            (dm, smooth(0.0, 24.0, (t - 1.5) / 1.0), true)
        } else if t < 4.5 {
            (smooth(dm, dn, (t - 3.0) / 1.2), 24.0, true)
        } else if t < 6.5 {
            (smooth(dn, df, (t - 4.5) / 1.6), 24.0, true)
        } else if t < 8.5 {
            let b = if t < 7.5 { smooth(24.0, 64.0, (t - 6.5) / 0.9) } else { smooth(64.0, 6.0, (t - 7.5) / 0.9) };
            (df, b, true)
        } else {
            (smooth(df, dm, (t - 8.5) / 1.2), smooth(6.0, 24.0, (t - 8.5) / 1.2), true)
        };
        // gentle sway for parallax
        let sway = (t * 0.6).sin() * 70.0;
        let f = |v: f32| Finite32::new(v).expect("finite");
        let camera = SceneCamera {
            position: Vec3 { x: f(640.0 + sway), y: f(330.0), z: base.position.z },
            target: Vec3 { x: f(640.0), y: f(370.0), z: f(0.0) },
            focus_px: on.then(|| f(focus)),
            blur_px: f(blur),
            ..base
        };
        let mk = |img, g| crate::Item { camera: Some(camera), ..item(img, Placement::Geometry(g), Crop::NONE, 1.0) };
        let items = [
            mk(&wall, geo((640.0, 330.0), (4200.0, 2625.0), 0.0, 0.0, -1100.0)),
            mk(&floor, geo((640.0, 760.0), (3200.0, 2600.0), 90.0, 0.0, -350.0)),
            mk(&far, geo((960.0, 400.0), (300.0, 375.0), 0.0, -12.0, -550.0)),
            mk(&mid, geo((560.0, 410.0), (300.0, 375.0), 0.0, 8.0, 0.0)),
            mk(&near, geo((390.0, 470.0), (240.0, 300.0), 0.0, 18.0, 380.0)),
        ];
        let scene = Scene {
            canvas: FrameSize::new(W, H).expect("nz"),
            background: Color::rgb(0.03, 0.03, 0.05),
            items: &items,
        };
        let snap = c.render(&scene, true).expect("render").pixels().expect("rb").clone();
        std::fs::write(format!("{dir}/frames/{i:04}.rgba"), snap.rgba()).expect("w");
        let label = if on { format!("focus {:.0} px  ·  blur {:.0} px", focus, blur) } else { "depth of field off".to_string() };
        writeln!(captions, "{label}").expect("w");
    }
}
