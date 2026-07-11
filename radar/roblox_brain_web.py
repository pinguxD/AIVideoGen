from __future__ import annotations

import json

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
            if plan:
                summary = f"""
                <p>
                  <b>Scene:</b> {esc(plan.scene.value)}
                  · <b>Core:</b> {esc(plan.core_mechanic.value)}
                  · <b>Supporting actions:</b>
                    {esc(", ".join(x.value for x in plan.supporting_actions) or "none")}
                  · <b>Confidence:</b> {esc(plan.overall_confidence)}%
                </p>
                """

            cards.append(
                f"""
                <div class="card">
                  <h3>{esc(source_name)}</h3>
                  {summary}
                  <form method="post" action="/roblox-brain/analyze">
                    <input type="hidden" name="source_name"
                           value="{esc(source_name)}">
                    <button type="submit">
                      Rebuild full Roblox Brain plan
                    </button>
                  </form>
                </div>
                """
            )

        return page(
            "Roblox Brain",
            f"""
            <h1>Roblox Brain - Part 2</h1>
            <div class="card">
              <p>
                Understands multiple gameplay actions, their roles and timing,
                plus UI, camera, editing, and audio timelines.
              </p>
            </div>
            {"".join(cards)}
            """,
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

        supporting = ", ".join(
            choice.value for choice in plan.supporting_actions
        ) or "none"

        action_rows = "".join(
            f"""
            <tr>
              <td>{esc(item.start)}</td>
              <td>{esc(item.end)}</td>
              <td>{esc(item.action)}</td>
              <td>{esc(item.action_kind)}</td>
              <td>{esc(item.role)}</td>
              <td>{esc(item.confidence)}%</td>
              <td>{esc(item.builder_id)}</td>
            </tr>
            """
            for item in plan.action_timeline
        )

        ui_rows = "".join(
            f"""
            <tr>
              <td>{esc(item.value)}</td>
              <td>{esc(item.confidence)}%</td>
              <td>{esc(item.builder_id)}</td>
              <td>{"<br>".join(esc(x) for x in item.evidence)}</td>
            </tr>
            """
            for item in plan.ui
        )

        builders = "".join(
            f"<li><code>{esc(builder)}</code></li>"
            for builder in plan.builder_sequence
        )

        execution_rows = "".join(
            f"""
            <tr>
              <td>{esc(item.get("order", ""))}</td>
              <td>{esc(item.get("phase", ""))}</td>
              <td>{esc(item.get("command", ""))}</td>
              <td>{esc(item.get("builder_id", ""))}</td>
            </tr>
            """
            for item in plan.execution_plan
        )

        environment_nodes = "".join(
            f"<li>{esc(node)}</li>"
            for node in plan.environment_graph.get("nodes", [])
        )

        why_rows = "".join(
            f"<div style='margin-bottom:12px'><b>✓ {esc(item.get('label', ''))}</b> — {esc(item.get('confidence', 0))}%<br>{esc(item.get('explanation', ''))}</div>"
            for item in plan.why_it_works
        ) or "<p>No clear retention drivers detected yet.</p>"
        difficulty_reasons = "<br>".join(
            esc(item) for item in plan.recreation_difficulty.get("reasons", [])
        ) or "No special difficulty factors."
        loop_rows = "".join(
            f"<tr><td>{esc(item.get('phase', ''))}</td><td>{esc(item.get('name', ''))}</td><td>{esc(item.get('command', ''))}</td><td>{esc(item.get('builder_id', ''))}</td><td><code>{esc(json.dumps(item, ensure_ascii=False))}</code></td></tr>"
            for item in plan.execution_loops
        )

        body = f"""
        <h1>Roblox Brain result</h1>

        <div class="grid">
          <div class="card">
            <div class="score">{esc(plan.scene.value)}</div>
            <p class="stat-label">Scene</p>
          </div>
          <div class="card">
            <div class="score">{esc(plan.core_mechanic.value)}</div>
            <p class="stat-label">Core mechanic</p>
          </div>
          <div class="card">
            <div class="score">{esc(plan.camera.value)}</div>
            <p class="stat-label">Base camera</p>
          </div>
        </div>

        <div class="card">
          <p><b>Continuous states:</b>
             {esc(", ".join(x.value for x in plan.state_actions) or "none")}</p>
          <p><b>Discrete actions:</b>
             {esc(", ".join(x.value for x in plan.event_actions) or "none")}</p>
          <p><b>Supporting actions:</b> {esc(supporting)}</p>
          <p><b>Complexity:</b> {esc(plan.complexity)}</p>
          <p><b>Generation mode:</b> {esc(plan.generation_mode)}</p>
          <p><b>Overall confidence:</b> {esc(plan.overall_confidence)}%</p>
          <p><b>Duration:</b> {esc(plan.duration)} seconds</p>
        </div>

        <div class="card">
          <h2>Gameplay action timeline</h2>
          <table>
            <thead>
              <tr>
                <th>Start</th><th>End</th><th>Action</th>
                <th>Kind</th><th>Role</th><th>Confidence</th><th>Builder</th>
              </tr>
            </thead>
            <tbody>{action_rows}</tbody>
          </table>
        </div>

        <div class="card">
          <h2>UI elements</h2>
          <table>
            <thead>
              <tr><th>UI</th><th>Confidence</th><th>Builder</th><th>Evidence</th></tr>
            </thead>
            <tbody>{ui_rows}</tbody>
          </table>
        </div>

        <div class="card">
          <h2>Character state</h2>
          <pre>{esc(json.dumps(plan.character_state, indent=2, ensure_ascii=False))}</pre>
        </div>

        <div class="card">
          <h2>Environment graph</h2>
          <ul>{environment_nodes}</ul>
          <pre>{esc(json.dumps(plan.environment_graph, indent=2, ensure_ascii=False))}</pre>
        </div>

        <div class="card">
          <h2>Camera style</h2>
          <p><b>Base camera:</b> {esc(plan.camera_pattern.get("base", "unknown"))}</p>
          <p><b>Dominant pattern:</b> {esc(plan.camera_pattern.get("dominant_pattern", "none"))}</p>
          <p><b>Occurrences:</b> {esc(plan.camera_pattern.get("occurrences", 0))}</p>
          <p><b>Average interval:</b> {esc(plan.camera_pattern.get("average_interval", "n/a"))}</p>
          <p><b>Pacing:</b> {esc(plan.camera_pattern.get("pacing", "unknown"))}</p>
        </div>

        <div class="card">
          <h2>Editing style</h2>
          <p><b>Dominant transition:</b> {esc(plan.editing_pattern.get("dominant_pattern", "none"))}</p>
          <p><b>Occurrences:</b> {esc(plan.editing_pattern.get("occurrences", 0))}</p>
          <p><b>Average interval:</b> {esc(plan.editing_pattern.get("average_interval", "n/a"))}</p>
          <p><b>Pacing:</b> {esc(plan.editing_pattern.get("pacing", "unknown"))}</p>
        </div>

        <div class="card">
          <h2>Audio style</h2>
          <p><b>Dominant effect:</b> {esc(plan.audio_pattern.get("dominant_pattern", "none"))}</p>
          <p><b>Occurrences:</b> {esc(plan.audio_pattern.get("occurrences", 0))}</p>
          <p><b>Average interval:</b> {esc(plan.audio_pattern.get("average_interval", "n/a"))}</p>
          <p><b>Pacing:</b> {esc(plan.audio_pattern.get("pacing", "unknown"))}</p>
        </div>

        <div class="card">
          <h2>Why it works</h2>
          {why_rows}
        </div>

        <div class="card">
          <h2>Recreation difficulty</h2>
          <div class="score">{esc(plan.recreation_difficulty.get("label", "Unknown"))}</div>
          <p><b>Difficulty score:</b> {esc(plan.recreation_difficulty.get("score", 0))}/100</p>
          <p><b>Fully procedural:</b> {esc(plan.recreation_difficulty.get("fully_procedural", False))}</p>
          <p><b>Reasons:</b><br>{difficulty_reasons}</p>
        </div>

        <div class="card">
          <h2>Video Blueprint</h2>
          <p><b>What is it?</b> {esc(plan.scene.value)} with {esc(plan.core_mechanic.value)}</p>
          <p><b>How is it made?</b> {esc(plan.camera_pattern.get("base", "unknown"))}, {esc(plan.editing_pattern.get("pacing", "unknown"))} editing, {esc(plan.audio_pattern.get("dominant_pattern", "none"))} audio pattern.</p>
          <p><b>Can it be built?</b> {esc(plan.generation_mode)} · {esc(plan.complexity)} complexity.</p>
        </div>

        <div class="card">
          <h2>Part 3 high-level execution loops</h2>
          <table>
            <thead><tr><th>Phase</th><th>Name</th><th>Command</th><th>Builder</th><th>Details</th></tr></thead>
            <tbody>{loop_rows}</tbody>
          </table>
        </div>

        <div class="card">
          <h2>Part 3 detailed execution plan</h2>
          <table>
            <thead>
              <tr><th>Order</th><th>Phase</th><th>Command</th><th>Builder</th></tr>
            </thead>
            <tbody>{execution_rows}</tbody>
          </table>
        </div>

        <div class="card">
          <h2>Unique builder sequence</h2>
          <ol>{builders}</ol>
        </div>

        <a class="btn" href="/roblox-brain">Back</a>
        """

        return page(
            "Roblox Brain result",
            body,
            "/roblox-brain",
        )
