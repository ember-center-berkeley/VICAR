// Edit project links, authors, and video sources here.
// Interactive recordings are generated in viewer-manifest.js.
window.VICAR = {
  "links": {
    "arxiv": "./",
    "paper": "./",
    "code": "https://github.com/ember-center-berkeley/VICAR",
    "video": "#skills"
  },
  "hero": {
    "video": "assets/videos/hero-box-pickup.mp4",
    "poster": "assets/images/hero-box-pickup-poster.jpg",
    "source": {
      "image": "assets/images/hero-human.jpg",
      "caption": "Human video",
      "alt": "Human demonstration from the overview figure: a person bends to lift a crate, face blurred."
    }
  },
  "authors": [],
  "affiliations": "",
  "abstract": "Third-person human videos offer a scalable alternative to task-specific reward engineering, teleoperation, and manually scripted demonstrations for humanoid loco-manipulation. Recent video-to-humanoid systems have shown that noisy human motion, object trajectories, and contacts can be extracted from unstructured videos and refined into deployable skills. However, a key gap remains for contact-rich imitation: the task is often defined by world-frame contacts whose poses, timing, and speed must survive embodiment mismatch and runtime scene changes. Towards this, we present VICAR (Video Imitation with Contact-Aware Retargeting), a pipeline for learning humanoid interactive skills from third-person human videos. The system first recovers human motion, reconstructs task-relevant obstacles from monocular video, and then retargets the motion to a humanoid while preserving global contact poses, motion speed, and collision clearance. Unlike retargeting methods that only remove penetration or preserve local interaction geometry, our formulation represents user-specified contact poses and collision clearance as high-priority Lagrangian penalty terms and optimizes the full motion to remain smooth through contact-rich transitions. The resulting motions are used to train a contact-conditioned motion generator whose inputs include movable contact points enabling runtime adaptation to new contact positions. We demonstrate the framework on ten diverse third-person video skills, including six table-tennis serves, three object-pickup tasks, and ladder climbing, and deploy the learned skills on hardware. These results suggest that contact-preserving retargeting is a practical step toward humanoids that learn useful interactive behavior by watching humans.",
  "bibtex": "",
  "serves": [
    {
      "id": "forehand",
      "title": "Simple forehand",
      "description": "A forward racket stroke with a movable hit point.",
      "tags": [
        "Forehand",
        "Serve"
      ],
      "src": "assets/videos/forehand.mp4?v=robot-match-1",
      "poster": "assets/images/forehand-poster.jpg?v=robot-match-1",
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
      "src": "assets/videos/backhand.mp4?v=robot-match-1",
      "poster": "assets/images/backhand-poster.jpg?v=robot-match-1",
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
      "src": "assets/videos/forehand-top-spin.mp4?v=robot-match-1",
      "poster": "assets/images/forehand-top-spin-poster.jpg?v=robot-match-1",
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
      "src": "assets/videos/backhand-top-spin.mp4?v=robot-match-1",
      "poster": "assets/images/backhand-top-spin-poster.jpg?v=robot-match-1",
      "captions": "",
      "width": 2560,
      "height": 720,
      "duration": 6
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
      "src": "assets/videos/ladder-climbing.mp4?v=robot-match-1",
      "poster": "assets/images/ladder-climbing-poster.jpg?v=robot-match-1",
      "captions": "",
      "width": 1166,
      "height": 864,
      "duration": 11.8,
      "wide": true,
      "comparison": "Timing aligned for comparison."
    }
  ]
};
