//! Scratch: renders the follow-cursor demo from a camera track the real follow camera
//! wrote (jstream-core's follow_track), not committed.
use std::io::Write;
use jstream_media::FrameSize;
use jstream_protocol::{Finite32, FitMode, ItemGeometry, SceneCamera, Size, Vec2};
use super::{item, open};
use crate::{Color, Crop, Placement, Scene};

#[test]
#[ignore]
fn follow_render() {
    let dir = std::env::var("REEL").expect("REEL dir");
    let f = |v: f32| Finite32::new(v).expect("finite");
    let cams: Vec<SceneCamera> = std::fs::read_to_string(format!("{dir}/cameras.jsonl")).expect("cams")
        .lines().map(|l| serde_json::from_str(l).expect("camera")).collect();
    let cursor: Vec<(f32, f32)> = std::fs::read_to_string(format!("{dir}/cursor.jsonl")).expect("cursor")
        .lines().map(|l| { let v: [f32; 2] = serde_json::from_str(l).expect("pt"); (v[0], v[1]) }).collect();
    let Some(mut opened) = open() else { panic!("no gpu") };
    let gpu = &mut opened.compositor;
    let ui = gpu.upload_rgba8(4320, 2700, &std::fs::read(format!("{dir}/ui.rgba")).expect("ui")).expect("upload");
    let arrow = gpu.upload_rgba8(48, 72, &std::fs::read(format!("{dir}/arrow.rgba")).expect("arrow")).expect("upload");
    let screen = ItemGeometry {
        fit_mode: FitMode::Stretch,
        ..ItemGeometry::try_new(Vec2::new(960.0, 540.0).expect("f"), Size::try_new(1440.0, 900.0).expect("p")).expect("g")
    };
    let mut out = std::fs::OpenOptions::new().write(true).open(format!("{dir}/frames.pipe")).expect("pipe");
    for (cam, c) in cams.iter().zip(&cursor) {
        let (x, y) = (c.0 - 720.0 + 960.0, c.1 - 450.0 + 540.0);
        // The pointer drawn into the capture, as a capture draws it: on the screen's plane.
        let tip = ItemGeometry {
            fit_mode: FitMode::Stretch,
            depth_px: f(0.2),
            ..ItemGeometry::try_new(Vec2::new(x + 8.0, y + 12.0).expect("f"), Size::try_new(16.0, 24.0).expect("p")).expect("g")
        };
        let items = [
            crate::Item { camera: Some(*cam), ..item(&ui, Placement::Geometry(screen), Crop::NONE, 1.0) },
            crate::Item { camera: Some(*cam), ..item(&arrow, Placement::Geometry(tip), Crop::NONE, 1.0) },
        ];
        let scene = Scene { canvas: FrameSize::new(1920, 1080).expect("nz"), background: Color::rgb(1.0, 0.0, 1.0), items: &items };
        let snap = gpu.render(&scene, true).expect("render").pixels().expect("rb").clone();
        out.write_all(snap.rgba()).expect("w");
    }
}
