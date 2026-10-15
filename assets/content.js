// Saved hero options: change the VICAR.hero preset key below to switch examples.
window.VICAR_HERO_PRESETS = {
  "ladder-climbing": {
    "objectPositionMobile": "98% 50%",
    "video": "assets/videos/hero-ladder-climbing.mp4?v=c0da56d3d265",
    "poster": "assets/images/hero-ladder-climbing-poster.jpg?v=c0da56d3d265",
    "source": {
      "image": "assets/images/hero-ladder-human.jpg",
      "caption": "Human video",
      "width": 462,
      "height": 610,
      "contacts": [
        {"x": 0.563, "y": 0.279, "label": "Hand grip on the ladder"},
        {"x": 0.420, "y": 0.656, "label": "Upper foot on the rung"},
        {"x": 0.355, "y": 0.772, "label": "Lower foot on the rung"}
      ],
      "alt": "Human ladder-climbing demonstration with red dots marking the hand grip and both foot contacts."
    }
  },
  "under-table-pickup": {
    "video": "assets/videos/hero-under-table-pickup.mp4?v=fe6d008a0aa9",
    "poster": "assets/images/hero-under-table-pickup-poster.jpg?v=fe6d008a0aa9",
    "source": {
      "image": "assets/images/idea-human.jpg",
      "caption": "Human video",
      "alt": "Human demonstration of under-table pickup: a person kneels beside a table and reaches underneath, with the supporting and grasping contacts marked. Face blurred."
    }
  }
};

// Edit project links, authors, and video sources here.
// Interactive recordings are generated in viewer-manifest.js.
window.VICAR = {
  "links": {
    "arxiv": "https://arxiv.org/abs/2610.13079",
    "paper": "assets/papers/VICAR.pdf?v=1fea09b04e1b",
    "code": "https://github.com/ember-center-berkeley/VICAR",
    "video": "#skills"
  },
  "hero": window.VICAR_HERO_PRESETS["ladder-climbing"],
  "humanReferences": {
    "forehand": {
      "image": "assets/images/human-references/forehand.jpg?v=2f40d03ca3f0",
      "width": 600,
      "height": 600,
      "alt": "Human demonstration of a forehand serve at racket contact."
    },
    "backhand": {
      "image": "assets/images/human-references/backhand.jpg?v=78e2574c3941",
      "width": 600,
      "height": 640,
      "alt": "Human demonstration of a backhand serve at racket contact."
    },
    "forehand-chop": {
      "image": "assets/images/human-references/forehand-chop.jpg?v=391c6548947d",
      "width": 600,
      "height": 640,
      "alt": "Human forehand top-spin demonstration at racket contact."
    },
    "backhand-chop": {
      "image": "assets/images/human-references/backhand-chop.jpg?v=bf3924ce8199",
      "width": 600,
      "height": 640,
      "alt": "Human backhand top-spin demonstration at racket contact."
    },
    "forehand-side-spin": {
      "image": "assets/images/human-references/forehand-side-spin.jpg?v=397c28420da0",
      "width": 600,
      "height": 638,
      "alt": "Human demonstration of a forehand side-spin serve."
    },
    "backhand-side-spin": {
      "image": "assets/images/human-references/backhand-side-spin.jpg?v=2f75f505b748",
      "width": 600,
      "height": 660,
      "alt": "Human demonstration of a backhand side-spin serve."
    },
    "tabletop-pickup": {
      "image": "assets/images/human-references/tabletop-pickup.jpg?v=fa35716d37f1",
      "width": 600,
      "height": 528,
      "alt": "Human demonstration reaching for an object on the tabletop."
    },
    "under-table-pickup": {
      "image": "assets/images/human-references/under-table-pickup.jpg?v=adb53dfa2ee6",
      "width": 600,
      "height": 454,
      "alt": "Human demonstration kneeling and reaching under the table to pick up an object."
    },
    "bimanual-pick-place": {
      "image": "assets/images/human-references/bimanual-pick-place.jpg?v=92ce02a59268",
      "width": 600,
      "height": 420,
      "alt": "Human demonstration grasping a crate on the ground with both hands."
    },
    "ladder-climbing": window.VICAR_HERO_PRESETS["ladder-climbing"].source
  },
  "authors": [],
  "affiliations": "",
  "abstract": "Third-person human videos offer a scalable alternative to task-specific reward engineering, teleoperation, and manually scripted demonstrations for humanoid loco-manipulation. Recent video-to-humanoid systems have shown that noisy human motion, object trajectories, and contacts can be extracted from unstructured videos and refined into deployable skills. However, a key gap remains for contact-rich imitation: the task is often defined by world-frame contacts whose poses, timing, and speed must survive embodiment mismatch and runtime scene changes. Towards this, we present VICAR (Video Imitation with Contact-Aware Retargeting), a pipeline for learning humanoid interactive skills from third-person human videos. The system first recovers human motion, reconstructs task-relevant obstacles from monocular video, and then retargets the motion to a humanoid while preserving global contact poses, motion speed, and collision clearance. Unlike retargeting methods that only remove penetration or preserve local interaction geometry, our formulation represents user-specified contact poses and collision clearance as high-priority Lagrangian penalty terms and optimizes the full motion to remain smooth through contact-rich transitions. The resulting motions are used to train a contact-conditioned motion generator whose inputs include movable contact points enabling runtime adaptation to new contact positions. We demonstrate the framework on ten diverse third-person video skills, including six table-tennis serves, three object-pickup tasks, and ladder climbing, and deploy the learned skills on hardware. These results suggest that contact-preserving retargeting is a practical step toward humanoids that learn useful interactive behavior by watching humans.",
  "bibtex": "",
  "serves": [
    {
      "id": "backhand-side-spin",
      "title": "Backhand side-spin",
      "description": "A backhand side-spin serve with a movable hit pose.",
      "tags": [
        "Backhand",
        "Serve"
      ],
      "src": "assets/videos/backhand-side-spin.mp4?v=robot-match-1",
      "poster": "assets/images/backhand-side-spin-poster.jpg?v=robot-match-1",
      "captions": "",
      "width": 2560,
      "height": 744
    },
    {
      "id": "forehand-side-spin",
      "title": "Forehand side-spin",
      "description": "A lateral racket motion retaining the demonstrated style.",
      "tags": [
        "Forehand",
        "Serve"
      ],
      "src": "assets/videos/forehand-side-spin.mp4?v=robot-match-1",
      "poster": "assets/images/forehand-side-spin-poster.jpg?v=robot-match-1",
      "captions": "",
      "width": 2560,
      "height": 720
    },
    {
      "id": "forehand",
      "title": "Simple forehand",
      "description": "A forward racket stroke with a movable hit point.",
      "tags": [
        "Forehand",
        "Serve"
      ],
      "src": "assets/videos/forehand.mp4?v=background-match-2",
      "poster": "assets/images/forehand-poster.jpg?v=background-match-2",
      "captions": "",
      "width": 2560,
      "height": 720,
      "duration": 6
    },
    {
      "id": "backhand",
      "title": "Simple backhand",
      "description": "A backhand stroke preserving the toss and hit interaction.",
      "tags": [
        "Backhand",
        "Serve"
      ],
      "src": "assets/videos/backhand.mp4?v=background-match-2",
      "poster": "assets/images/backhand-poster.jpg?v=background-match-2",
      "captions": "",
      "width": 2560,
      "height": 720,
      "duration": 6
    },
    {
      "id": "backhand-top-spin",
      "title": "Backhand top-spin",
      "description": "A backhand top-spin serve executed on the humanoid.",
      "tags": [
        "Backhand",
        "Serve"
      ],
      "src": "assets/videos/backhand-top-spin.mp4?v=background-match-2",
      "poster": "assets/images/backhand-top-spin-poster.jpg?v=background-match-2",
      "captions": "",
      "width": 2560,
      "height": 720,
      "duration": 6
    },
    {
      "id": "forehand-top-spin",
      "title": "Forehand top-spin",
      "description": "A forehand top-spin serve executed on the humanoid.",
      "tags": [
        "Forehand",
        "Serve"
      ],
      "src": "assets/videos/forehand-top-spin.mp4?v=background-match-2",
      "poster": "assets/images/forehand-top-spin-poster.jpg?v=background-match-2",
      "captions": "",
      "width": 2560,
      "height": 720,
      "duration": 6
    }
  ],
  "skills": [
    {
      "id": "tabletop-pickup",
      "title": "Tabletop pickup",
      "description": "Reach for an object on the table while preserving its grasp pose.",
      "tags": [
        "Object interaction",
        "Hardware"
      ],
      "art": "pickup",
      "src": "assets/videos/tabletop-pickup.mp4?v=robot-match-1",
      "poster": "assets/images/tabletop-pickup-poster.jpg?v=robot-match-1",
      "captions": "",
      "width": 2560,
      "height": 720,
      "comparison": "Human demonstration (left) · Robot execution (right)"
    },
    {
      "id": "under-table-pickup",
      "title": "Under-table pickup",
      "description": "Maintain right-hand table-edge support while the left hand reaches below.",
      "tags": [
        "Support contact",
        "Hardware"
      ],
      "art": "under-table",
      "src": "assets/videos/under-table-pickup.mp4?v=robot-match-1",
      "poster": "assets/images/under-table-pickup-poster.jpg?v=robot-match-1",
      "captions": "",
      "width": 2560,
      "height": 720,
      "comparison": "Human demonstration (left) · Robot execution (right)"
    },
    {
      "id": "bimanual-pick-place",
      "title": "Bimanual pick-and-place",
      "description": "Synchronize both hands to lift a box from the ground and place it on the table.",
      "tags": [
        "Two-hand coordination",
        "Hardware"
      ],
      "art": "bimanual",
      "src": "assets/videos/bimanual-pick-place.mp4?v=robot-match-1",
      "poster": "assets/images/bimanual-pick-place-poster.jpg?v=robot-match-1",
      "captions": "",
      "width": 2560,
      "height": 720,
      "comparison": "Human demonstration (left) · Robot execution (right)"
    },
    {
      "id": "ladder-climbing",
      "title": "Ladder climbing",
      "description": "Coordinate sequential hand and foot contacts with the ladder supports.",
      "tags": [
        "Whole-body coordination",
        "Simulation"
      ],
      "art": "ladder",
      "src": "assets/videos/ladder-climbing.mp4?v=reference-20261009",
      "poster": "assets/images/ladder-climbing-poster.jpg?v=reference-20261009",
      "captions": "",
      "width": 984,
      "height": 864,
      "duration": 11.8,
      "wide": true,
      "comparison": "Timing aligned for comparison."
    }
  ]
};
