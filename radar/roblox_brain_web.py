from __future__ import annotations

from flask import request

from .reference_library import list_reference_runs
from .roblox_brain import (
    build_roblox_brain_plan,
    load_roblox_brain_plan,
)


def register_roblox_brain_routes(app, page, esc) -> None:
    @app.route("/roblox-brain")
    def roblox_brain_page():
        references = [
            item
            for item in list_reference_runs(limit=500)
            if str(item.get("status") or "") == "ANALYZED"
        ]

        cards = []
        for item in references:
            source_name = str(item.get("source_name") or "")
            plan = load_roblox_brain_plan(source_name)

            summary = ""
            if plan is not None:
                summary = f"""
                <p>
                  <b>Scene:</b> {esc(plan.scene.value)}
                  · <b>Mechanic:</b> {esc(plan.mechanic.value)}
                  · <b>Camera:</b> {esc(plan.camera.value)}
                  · <b>Confidence:</b>
                    {esc(plan.overall_confidence)}%
                </p>
                """

            cards.append(
                f"""
                <div class="card">
                  <h3>{esc(source_name)}</h3>
                  {summary}
                  <form method="post"
                        action="/roblox-brain/analyze">
                    <input type="hidden"
                           name="source_name"
                           value="{esc(source_name)}">
                    <button type="submit">
                      Build Roblox Brain plan
                    </button>
                  </form>
                </div>
                """
            )

        body = f"""
        <h1>Roblox Brain - Part 2</h1>

        <div class="card">
          <p>
            Converts recreation analysis into reusable Roblox concepts:
            scene, mechanic, camera, UI, lighting, and builder modules.
          </p>
        </div>

        {"".join(cards)}
        """

        return page(
            "Roblox Brain",
            body,
            "/roblox-brain",
        )

    @app.route("/roblox-brain/analyze", methods=["POST"])
    def roblox_brain_analyze():
        source_name = str(request.form.get("source_name") or "").strip()

        try:
            plan = build_roblox_brain_plan(source_name)
        except Exception as exc:
            return page(
                "Roblox Brain failed",
                f"""
                <h1>Roblox Brain failed</h1>
                <div class="card"><pre>{esc(exc)}</pre></div>
                <a class="btn" href="/roblox-brain">Back</a>
                """,
                "/roblox-brain",
            ), 500

        ui_rows = "".join(
            f"""
            <tr>
              <td>{esc(choice.value)}</td>
              <td>{esc(choice.confidence)}%</td>
              <td>{esc(choice.builder_id)}</td>
              <td>{"<br>".join(esc(x) for x in choice.evidence)}</td>
            </tr>
            """
            for choice in plan.ui
        )

        builder_rows = "".join(
            f"<li><code>{esc(builder)}</code></li>"
            for builder in plan.builder_sequence
        )

        missing = "<br>".join(
            esc(item) for item in plan.required_assets
        ) or "Nothing required."

        body = f"""
        <h1>Roblox Brain result</h1>

        <div class="grid">
          <div class="card">
            <div class="score">{esc(plan.scene.value)}</div>
            <p class="stat-label">Scene</p>
          </div>
          <div class="card">
            <div class="score">{esc(plan.mechanic.value)}</div>
            <p class="stat-label">Mechanic</p>
          </div>
          <div class="card">
            <div class="score">{esc(plan.camera.value)}</div>
            <p class="stat-label">Camera</p>
          </div>
        </div>

        <div class="card">
          <p><b>Generation mode:</b>
             {esc(plan.generation_mode)}</p>
          <p><b>Overall confidence:</b>
             {esc(plan.overall_confidence)}%</p>
          <p><b>Lighting:</b> {esc(plan.lighting)}</p>
          <p><b>Duration:</b> {esc(plan.duration)} seconds</p>
          <p><b>Required assets:</b><br>{missing}</p>
        </div>

        <div class="card">
          <h2>Scene decision</h2>
          <p><b>{esc(plan.scene.value)}</b>
             - {esc(plan.scene.confidence)}%</p>
          <p>{"<br>".join(esc(x) for x in plan.scene.evidence)}</p>
        </div>

        <div class="card">
          <h2>Mechanic decision</h2>
          <p><b>{esc(plan.mechanic.value)}</b>
             - {esc(plan.mechanic.confidence)}%</p>
          <p>{"<br>".join(esc(x) for x in plan.mechanic.evidence)}</p>
        </div>

        <div class="card">
          <h2>Camera decision</h2>
          <p><b>{esc(plan.camera.value)}</b>
             - {esc(plan.camera.confidence)}%</p>
          <p>{"<br>".join(esc(x) for x in plan.camera.evidence)}</p>
        </div>

        <div class="card">
          <h2>UI decisions</h2>
          <table>
            <thead>
              <tr>
                <th>UI</th>
                <th>Confidence</th>
                <th>Builder</th>
                <th>Evidence</th>
              </tr>
            </thead>
            <tbody>{ui_rows}</tbody>
          </table>
        </div>

        <div class="card">
          <h2>Part 3 builder sequence</h2>
          <ol>{builder_rows}</ol>
        </div>

        <a class="btn" href="/roblox-brain">Back</a>
        """

        return page(
            "Roblox Brain result",
            body,
            "/roblox-brain",
        )
