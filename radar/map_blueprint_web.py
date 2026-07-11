from __future__ import annotations

import json

from flask import request, send_file

from .full_video_analyzer import BASE
from .map_blueprint import (
    approve_map_blueprint,
    build_map_blueprint,
    load_map_blueprint,
    update_map_blueprint,
)
from .reference_library import list_reference_runs


def register_map_blueprint_routes(app, page, esc) -> None:
    @app.route("/map-blueprint")
    def map_blueprint_home():
        references = [
            item
            for item in list_reference_runs(limit=500)
            if str(item.get("status") or "") == "ANALYZED"
        ]

        cards = []
        for item in references:
            source_name = str(item.get("source_name") or "")
            blueprint = load_map_blueprint(source_name)
            status = blueprint.status if blueprint else "NOT BUILT"
            summary = ""
            review_button = ""
            if blueprint:
                summary = (
                    "<p><b>Type:</b> "
                    + esc(blueprint.map_type)
                    + " · <b>Sky:</b> "
                    + esc(blueprint.sky_visibility)
                    + "% · <b>Structures:</b> "
                    + esc(len(blueprint.structures))
                    + " · <b>Confidence:</b> "
                    + esc(blueprint.topology_confidence)
                    + "%</p>"
                )
                review_button = (
                    '<a class="btn" href="/map-blueprint/review/'
                    + esc(source_name)
                    + '">Review Blueprint</a>'
                )

            cards.append(
                """
                <div class="card">
                  <h3>{source}</h3>
                  <p><b>Status:</b> {status}</p>
                  {summary}
                  <form method="post"
                        action="/map-blueprint/build"
                        style="display:inline-block;margin-right:8px">
                    <input type="hidden"
                           name="source_name"
                           value="{source}">
                    <button type="submit">
                      Watch Full Video &amp; Build Blueprint
                    </button>
                  </form>
                  {review}
                </div>
                """.format(
                    source=esc(source_name),
                    status=esc(status),
                    summary=summary,
                    review=review_button,
                )
            )

        body = """
        <h1>Full-Video Map Blueprint</h1>
        <div class="card">
          <p>
            The analyzer watches the full video, masks fixed overlays and the
            central avatar area, tracks repeated geometry across frames, merges
            duplicate views, classifies platforms, walkways, trigger pads and
            shared backdrop walls, then creates one coherent map before Roblox
            generation is allowed.
          </p>
        </div>
        {cards}
        """.format(cards="".join(cards))

        return page("Map Blueprint", body, "/map-blueprint")

    @app.route("/map-blueprint/build", methods=["POST"])
    def map_blueprint_build():
        source_name = str(request.form.get("source_name") or "").strip()
        try:
            build_map_blueprint(source_name)
        except Exception as exc:
            return page(
                "Blueprint failed",
                """
                <h1>Map Blueprint failed</h1>
                <div class="card"><pre>{error}</pre></div>
                <a class="btn" href="/map-blueprint">Back</a>
                """.format(error=esc(exc)),
                "/map-blueprint",
            ), 500
        return _review_page(source_name, page, esc)

    @app.route("/map-blueprint/review/<path:source_name>")
    def map_blueprint_review(source_name: str):
        return _review_page(source_name, page, esc)

    @app.route("/map-blueprint/approve", methods=["POST"])
    def map_blueprint_approve():
        source_name = str(request.form.get("source_name") or "").strip()
        approve_map_blueprint(source_name)
        return _review_page(source_name, page, esc)

    @app.route("/map-blueprint/regenerate", methods=["POST"])
    def map_blueprint_regenerate():
        source_name = str(request.form.get("source_name") or "").strip()
        build_map_blueprint(source_name)
        return _review_page(source_name, page, esc)

    @app.route("/map-blueprint/edit", methods=["POST"])
    def map_blueprint_edit():
        source_name = str(request.form.get("source_name") or "").strip()
        raw = str(request.form.get("blueprint_json") or "")
        try:
            payload = json.loads(raw)
            update_map_blueprint(source_name, payload)
        except Exception as exc:
            return page(
                "Blueprint edit failed",
                """
                <h1>Blueprint edit failed</h1>
                <div class="card"><pre>{error}</pre></div>
                <a class="btn" href="/map-blueprint/review/{source}">
                  Back
                </a>
                """.format(
                    error=esc(exc),
                    source=esc(source_name),
                ),
                "/map-blueprint",
            ), 400
        return _review_page(source_name, page, esc)

    @app.route("/map-blueprint/image/<kind>/<path:source_name>")
    def map_blueprint_image(kind: str, source_name: str):
        blueprint = load_map_blueprint(source_name)
        if not blueprint:
            return "Blueprint not found.", 404
        relative = (
            blueprint.preview_path
            if kind == "preview"
            else blueprint.contact_sheet_path
        )
        image_path = BASE / relative
        if not image_path.exists():
            return "Image missing: " + str(image_path), 404
        return send_file(image_path)


def _review_page(source_name, page, esc):
    blueprint = load_map_blueprint(source_name)
    if blueprint is None:
        return page(
            "Blueprint missing",
            """
            <h1>No Map Blueprint exists yet</h1>
            <a class="btn" href="/map-blueprint">Back</a>
            """,
            "/map-blueprint",
        ), 404

    editable = {
        "map_type": blueprint.map_type,
        "enclosure": blueprint.enclosure,
        "sky_visibility": blueprint.sky_visibility,
        "structures": [
            {
                "structure_id": item.structure_id,
                "structure_type": item.structure_type,
                "confidence": item.confidence,
                "observations": item.observations,
                "first_seen": item.first_seen,
                "last_seen": item.last_seen,
                "screen_bbox": list(item.screen_bbox),
                "relative_depth": item.relative_depth,
                "color_rgb": list(item.color_rgb),
                "world_size": list(item.world_size),
                "world_position": list(item.world_position),
                "shared": item.shared,
                "mechanic": item.mechanic,
                "notes": item.notes,
            }
            for item in blueprint.structures
        ],
    }

    structure_rows = []
    for item in blueprint.structures:
        structure_rows.append(
            """
            <tr>
              <td>{id}</td>
              <td>{type}</td>
              <td>{depth}</td>
              <td>{seen}</td>
              <td>{confidence}%</td>
              <td>{position}</td>
              <td>{size}</td>
              <td>{mechanic}</td>
            </tr>
            """.format(
                id=esc(item.structure_id),
                type=esc(item.structure_type),
                depth=esc(item.relative_depth),
                seen=esc(item.observations),
                confidence=esc(item.confidence),
                position=esc(item.world_position),
                size=esc(item.world_size),
                mechanic=esc(item.mechanic),
            )
        )
    if not structure_rows:
        structure_rows.append(
            '<tr><td colspan="8">No structures detected.</td></tr>'
        )

    rules = "".join(
        "<tr><td>{}</td><td>{}</td></tr>".format(
            esc(key),
            esc(value),
        )
        for key, value in blueprint.rules.items()
    )
    unresolved = "".join(
        "<li>{}</li>".format(
            esc(item.get("message", item))
        )
        for item in blueprint.unresolved
    ) or "<li>None</li>"

    generate_section = (
        """
        <form method="post"
              action="/creator-ai-v2/generate"
              style="display:inline-block">
          <input type="hidden"
                 name="source_name"
                 value="{source}">
          <button type="submit">Generate Roblox Place</button>
        </form>
        """.format(source=esc(source_name))
        if blueprint.status == "APPROVED"
        else "<p><b>Approve the Map Blueprint before Roblox generation.</b></p>"
    )

    body = """
    <h1>Map Blueprint Review</h1>

    <div class="grid">
      <div class="card">
        <div class="score">{status}</div>
        <p>Blueprint status</p>
      </div>
      <div class="card">
        <div class="score">{confidence}%</div>
        <p>Topology confidence</p>
      </div>
      <div class="card">
        <div class="score">{frames}</div>
        <p>Frames examined</p>
      </div>
    </div>

    <div class="card">
      <p><b>Map type:</b> {map_type}</p>
      <p><b>Enclosure:</b> {enclosure}</p>
      <p><b>Sky visibility:</b> {sky}%</p>
      <p><b>Depth order:</b> {depth_order}</p>
    </div>

    <div class="grid">
      <div class="card">
        <h2>Top-down Map Preview</h2>
        <img src="/map-blueprint/image/preview/{source}"
             style="max-width:100%;border-radius:8px">
      </div>
      <div class="card">
        <h2>Full-video Evidence</h2>
        <img src="/map-blueprint/image/contact/{source}"
             style="max-width:100%;border-radius:8px">
      </div>
    </div>

    <div class="card">
      <h2>Tracked structures</h2>
      <table>
        <thead>
          <tr>
            <th>ID</th><th>Type</th><th>Depth</th><th>Seen</th>
            <th>Confidence</th><th>World position</th>
            <th>World size</th><th>Mechanic</th>
          </tr>
        </thead>
        <tbody>{structure_rows}</tbody>
      </table>
    </div>

    <div class="card">
      <h2>Builder safety rules</h2>
      <table><tbody>{rules}</tbody></table>
    </div>

    <div class="card">
      <h2>Unresolved evidence</h2>
      <ul>{unresolved}</ul>
    </div>

    <div class="card">
      <h2>Edit Map Blueprint JSON</h2>
      <p>
        Correct types, positions, sizes or remove structures before approval.
        Saving an edit returns the blueprint to DRAFT.
      </p>
      <form method="post" action="/map-blueprint/edit">
        <input type="hidden"
               name="source_name"
               value="{source}">
        <textarea name="blueprint_json"
                  style="width:100%;height:420px;font-family:monospace">{editable}</textarea>
        <button type="submit">Save Blueprint Edits</button>
      </form>
    </div>

    <div class="card">
      <form method="post"
            action="/map-blueprint/approve"
            style="display:inline-block;margin-right:8px">
        <input type="hidden"
               name="source_name"
               value="{source}">
        <button type="submit">Approve Map</button>
      </form>

      <form method="post"
            action="/map-blueprint/regenerate"
            style="display:inline-block;margin-right:8px">
        <input type="hidden"
               name="source_name"
               value="{source}">
        <button type="submit">Regenerate Analysis</button>
      </form>

      {generate_section}
    </div>

    <a class="btn" href="/map-blueprint">Back</a>
    """.format(
        status=esc(blueprint.status),
        confidence=esc(blueprint.topology_confidence),
        frames=esc(blueprint.frames_examined),
        map_type=esc(blueprint.map_type),
        enclosure=esc(blueprint.enclosure),
        sky=esc(blueprint.sky_visibility),
        depth_order=esc(" → ".join(blueprint.depth_order)),
        source=esc(source_name),
        structure_rows="".join(structure_rows),
        rules=rules,
        unresolved=unresolved,
        editable=esc(json.dumps(editable, indent=2)),
        generate_section=generate_section,
    )

    return page(
        "Map Blueprint Review",
        body,
        "/map-blueprint",
    )
