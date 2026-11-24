//! Bakes jstream-demos.json from tools/build_demos.py's output, with JStream's own
//! collection code: it loads build/tour.json, applies build/cockpit-edits.json one edit at
//! a time as the engine would, and saves the project in the canonical form JStream writes,
//! checking it loads back unchanged.
//!
//! Copy this file into a JStream checkout as crates/jstream-graph/tests/bake_demos.rs and run
//!
//!     DEMOS=/path/to/StreamingScenes cargo test -p jstream-graph --test bake_demos
//!
//! It writes $DEMOS/jstream-demos.json.

use jstream_graph::Graph;
use jstream_protocol::{Edit, KindDescriptor};

fn kinds() -> Vec<KindDescriptor> {
    let snap = include_str!("../../jstream-core/schema/kinds.snap");
    let start = snap.find('[').expect("the kinds snapshot holds a JSON list");
    serde_json::from_str(&snap[start..]).expect("the kinds snapshot parses")
}

#[test]
fn bake_demos() {
    let Some(root) = std::env::var_os("DEMOS") else {
        return;
    };
    let root = std::path::PathBuf::from(root);
    let read = |name: &str| std::fs::read_to_string(root.join("build").join(name)).expect(name);
    let mut graph = Graph::new()
        .with_kinds(kinds())
        .with_collection_json(&read("tour.json"))
        .expect("the tour loads");
    let edits: Vec<serde_json::Value> =
        serde_json::from_str(&read("cockpit-edits.json")).expect("the edits parse");
    for (n, value) in edits.into_iter().enumerate() {
        let edit: Edit = serde_json::from_value(value.clone())
            .unwrap_or_else(|e| panic!("edit {n} doesn't parse: {e}: {value}"));
        if let Err(e) = graph.apply(&[edit], None) {
            panic!("edit {n} doesn't apply: {e:?}: {value}");
        }
    }
    let saved = graph.to_collection_json();
    let again = Graph::new()
        .with_kinds(kinds())
        .with_collection_json(&saved)
        .expect("the project loads back")
        .to_collection_json();
    assert_eq!(saved, again, "the project saves back unchanged");
    std::fs::write(root.join("jstream-demos.json"), saved).expect("writes the project");
}
