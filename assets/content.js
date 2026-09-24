// Edit project links, authors, video sources, and Viser recordings here.
// Empty video sources display intentional placeholders; missing links point home.
window.VICAR = {
  "links": {
    "arxiv": "./",
    "paper": "./",
    "code": "https://github.com/ember-center-berkeley/VICAR",
    "video": "./"
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
      "src": "",
      "poster": "",
      "captions": ""
    },
    {
      "id": "backhand",
      "title": "Simple backhand",
      "description": "A backhand stroke preserving the toss and hit interaction.",
      "tags": [
        "Backhand",
        "Serve"
      ],
      "src": "",
      "poster": "",
      "captions": ""
    },
    {
      "id": "forehand-chop",
      "title": "Forehand chop",
      "description": "A chopping motion with contact-aware racket retargeting.",
      "tags": [
        "Forehand",
        "Serve"
      ],
      "src": "",
      "poster": "",
      "captions": ""
    },
    {
      "id": "backhand-chop",
      "title": "Backhand chop",
      "description": "A backhand chop with a contact-conditioned reference.",
      "tags": [
        "Backhand",
        "Serve"
      ],
      "src": "",
      "poster": "",
      "captions": ""
    },
    {
      "id": "forehand-side-spin",
      "title": "Forehand side-spin",
      "description": "A lateral racket motion retaining the demonstrated style.",
      "tags": [
        "Forehand",
        "Serve"
      ],
      "src": "",
      "poster": "",
      "captions": ""
    },
    {
      "id": "backhand-side-spin",
      "title": "Backhand side-spin",
      "description": "A backhand side-spin serve with a movable hit pose.",
      "tags": [
        "Backhand",
        "Serve"
      ],
      "src": "",
      "poster": "",
      "captions": ""
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
      "src": "",
      "poster": "",
      "captions": ""
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
      "src": "",
      "poster": "",
      "captions": ""
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
      "src": "",
      "poster": "",
      "captions": ""
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
      "src": "",
      "poster": "",
      "captions": ""
    }
  ],
  "viewer": {
    "client": "viser-client/",
    "scenes": [
      {
        "id": "serve",
        "title": "Table-tennis serve",
        "description": "A schematic motion example to preview the interaction. Replace with VICAR recordings for research results.",
        "illustrative": true,
        "variants": [
          {
            "id": "original",
            "label": "Original",
            "recording": "assets/recordings/serve-original.viser"
          },
          {
            "id": "left",
            "label": "Shift left",
            "recording": "assets/recordings/serve-left.viser"
          },
          {
            "id": "right",
            "label": "Shift right",
            "recording": "assets/recordings/serve-right.viser"
          },
          {
            "id": "forward",
            "label": "Move forward",
            "recording": "assets/recordings/serve-forward.viser"
          },
          {
            "id": "higher",
            "label": "Move higher",
            "recording": "assets/recordings/serve-higher.viser"
          }
        ]
      },
      {
        "id": "pickup",
        "title": "Object pickup",
        "description": "A schematic motion example to preview the interaction. Replace with VICAR recordings for research results.",
        "illustrative": true,
        "variants": [
          {
            "id": "original",
            "label": "Original",
            "recording": "assets/recordings/pickup-original.viser"
          },
          {
            "id": "left",
            "label": "Shift left",
            "recording": "assets/recordings/pickup-left.viser"
          },
          {
            "id": "right",
            "label": "Shift right",
            "recording": "assets/recordings/pickup-right.viser"
          },
          {
            "id": "forward",
            "label": "Move forward",
            "recording": "assets/recordings/pickup-forward.viser"
          },
          {
            "id": "higher",
            "label": "Move higher",
            "recording": "assets/recordings/pickup-higher.viser"
          }
        ]
      }
    ]
  }
};
