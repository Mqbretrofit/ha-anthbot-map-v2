"""Regression test for the Genie resume command recovered from the app."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
BUTTON_SOURCE = ROOT / "custom_components" / "anthbot_map" / "button.py"
CARD_SOURCE = ROOT / "custom_components" / "anthbot_map" / "frontend" / "anthbot-map-card.js"
I18N_SOURCE = ROOT / "custom_components" / "anthbot_map" / "frontend" / "i18n.js"
STYLES_SOURCE = ROOT / "custom_components" / "anthbot_map" / "frontend" / "styles.css"
COORDINATOR_SOURCE = ROOT / "custom_components" / "anthbot_map" / "coordinator.py"
INIT_SOURCE = ROOT / "custom_components" / "anthbot_map" / "__init__.py"


class ResumeCommandTests(unittest.TestCase):
    def test_resume_restarts_the_remembered_task(self) -> None:
        source = BUTTON_SOURCE.read_text(encoding="utf-8")
        block = source.split('elif key == "resume_mow":', 1)[1].split(
            'elif key == "pause_mow":', 1
        )[0]
        self.assertIn("self.coordinator.last_mowing_task", block)
        self.assertIn("There is no mowing task to resume", block)
        self.assertIn('task_type == "full"', block)
        self.assertIn('task_type == "manual_zone"', block)
        self.assertIn('task_type == "edge"', block)
        self.assertIn('task_type == "dock_edge"', block)
        self.assertIn('cmd="custom_area_mow_start", data=data', block)
        self.assertNotIn('cmd="mow_continue"', block)

    def test_card_checks_home_assistant_task_before_resume(self) -> None:
        source = CARD_SOURCE.read_text(encoding="utf-8")
        self.assertIn('command === "resume"', source)
        self.assertIn("attributes?.last_mowing_task", source)
        self.assertIn('translate(anthbotFeedbackLanguage(card, hass), "noTaskToResume")', source)
        self.assertNotIn("anthbot:last-mowing-target:", source)

    def test_control_panel_uses_one_dynamic_app_style_action(self) -> None:
        source = CARD_SOURCE.read_text(encoding="utf-8")
        panel = source.split("renderControlPanel(body)", 1)[1].split("renderSettingsPanel", 1)[0]
        self.assertIn("createPrimaryMowingTile(action)", panel)
        self.assertNotIn('createCommandTile(this.t("pauseTask")', panel)
        self.assertNotIn('createCommandTile(this.t("resumeTask")', panel)
        self.assertIn("selectedMowingTarget", panel)
        self.assertIn("currentAutoZones()", panel)
        self.assertIn('selectedMowingTarget = { type: "edge" }', panel)
        self.assertIn('selectedMowingTarget = { type: "dock-edge" }', panel)
        self.assertIn('handleCommand("dock-edge")', source)
        self.assertIn("body.appendChild(targetGrid)", panel)
        self.assertIn("body.appendChild(actionGrid)", panel)
        self.assertIn('start: [this.t("startLabel"), this.t("startSelectedTask")]', source)
        self.assertNotIn('content:"✓ "', source)

    def test_selected_task_start_is_translated_for_all_languages(self) -> None:
        source = I18N_SOURCE.read_text(encoding="utf-8")
        block = source.split("const selectedTaskStartTranslations = {", 1)[1].split("};", 1)[0]
        for language in ("en", "hu", "de", "fr", "es", "it", "pt", "nl", "pl", "cs", "sk", "ro", "da", "sv", "no", "fi", "zh-CN", "zh-TW", "tr", "th", "vi", "ko", "km"):
            self.assertIn(f'{language}:', block.replace('"', ''))

    def test_diagnostics_maintenance_values_use_the_same_components(self) -> None:
        source = CARD_SOURCE.read_text(encoding="utf-8")
        self.assertIn('[this.t("bladeLife"), "rechargeContactLife"]', source)
        self.assertIn('[this.t("cameraLife"), "cuttingLineLife"]', source)
        self.assertIn('[this.t("dockContact"), "cuttingComponentsLife"]', source)


    def test_beta35_command_route_is_kept_for_panel_commands(self) -> None:
        source = CARD_SOURCE.read_text(encoding="utf-8")
        self.assertNotIn("if (control.closest?.('[data-role=\"panel-body\"]')) return;", source)
        self.assertIn("void executeAnthbotCommand(hass, card, command, details, control, config);", source)

    def test_primary_action_is_not_overridden_by_global_start_handler(self) -> None:
        source = CARD_SOURCE.read_text(encoding="utf-8")
        self.assertIn("tile.dataset.primaryMowingAction = action", source)
        self.assertIn('if (control.matches?.("[data-primary-mowing-action]")) return;', source)

    def test_single_zone_uses_the_beta35_zone_button_route(self) -> None:
        source = CARD_SOURCE.read_text(encoding="utf-8")
        self.assertIn("this.selectedMowingTarget.zones.length === 1", source)
        self.assertIn("await this.startZone(this.selectedMowingTarget.zones[0])", source)
        self.assertIn("await this.startAutoZone(this.selectedMowingTarget.zones[0])", source)

    def test_legacy_duplicate_command_dock_is_removed(self) -> None:
        source = CARD_SOURCE.read_text(encoding="utf-8")
        self.assertNotIn('<div class="map-overlay command-dock">', source)
        self.assertNotIn('root.querySelector(".command-dock")', source)

    def test_zone_targets_support_multiple_selection_and_order(self) -> None:
        source = CARD_SOURCE.read_text(encoding="utf-8")
        self.assertIn('createMowingZoneGroup("zone-set"', source)
        self.assertIn('createMowingZoneGroup("auto-zone-set"', source)
        self.assertIn("moveSelectedZone(type, index, offset, body)", source)
        self.assertIn("await this.startZones(this.selectedMowingTarget.zones)", source)
        self.assertIn("await this.startAutoZones(this.selectedMowingTarget.zones)", source)
        self.assertIn("zones: zones.map((zone) => zone.id ?? zone.name)", source)

    def test_zone_picker_preserves_fold_state_and_stable_multi_selection(self) -> None:
        source = CARD_SOURCE.read_text(encoding="utf-8")
        self.assertIn('this.mowingZoneGroupsOpen = { "zone-set": true, "auto-zone-set": false }', source)
        self.assertIn("details.open = Boolean(this.mowingZoneGroupsOpen[type])", source)
        self.assertIn("this.mowingZoneGroupsOpen[type] = details.open", source)
        self.assertIn("event.preventDefault()", source)
        self.assertIn("event.stopPropagation()", source)
        self.assertIn("current.push(zone)", source)
        self.assertIn(".mowing-target-tile.active,.mowing-target-tile.active:hover", source)

    def test_live_refresh_does_not_consume_the_first_panel_click(self) -> None:
        source = CARD_SOURCE.read_text(encoding="utf-8")
        self.assertIn("this.panelInteractionUntil = 0", source)
        self.assertIn('panelBody?.addEventListener("pointerdown"', source)
        self.assertIn("this.panelInteractionUntil = Date.now() + 1200", source)
        self.assertIn("Date.now() >= this.panelInteractionUntil", source)
        self.assertIn('["SELECT", "INPUT"]', source)

    def test_mobile_layout_matches_garden_map_card_behavior(self) -> None:
        source = CARD_SOURCE.read_text(encoding="utf-8")
        self.assertIn('.canvas-wrap.auto-map-size', source)
        self.assertIn('height:calc(100dvh - 78px)', source)
        self.assertIn('max-height:76%', source)
        self.assertIn('window.matchMedia("(max-width: 720px)").matches', source)
        self.assertIn('this.config.mobile_map_rotation ?? this.config.mobileMapRotation ?? 90', source)
        self.assertIn('this.config.mobile_map_fit || this.config.mobileMapFit || "contain"', source)
        self.assertIn('this.config.mobile_robot_size ?? this.config.mobileRobotSize ?? 24', source)

    def test_panel_tabs_wrap_and_selected_tiles_have_readable_contrast(self) -> None:
        card = CARD_SOURCE.read_text(encoding="utf-8")
        styles = STYLES_SOURCE.read_text(encoding="utf-8")
        self.assertIn(
            "grid-template-columns: repeat(auto-fit, minmax(min(100%, 170px), 1fr));",
            styles,
        )
        self.assertIn("white-space: normal;", styles)
        self.assertIn("overflow-wrap: anywhere;", styles)
        self.assertIn(".panel-tabs button.active", styles)
        self.assertIn("color: #07140c;", styles)
        self.assertIn("color:#07140c !important", card)

    def test_live_pose_has_priority_over_stale_mapping_pose(self) -> None:
        source = CARD_SOURCE.read_text(encoding="utf-8")
        self.assertIn(
            "[rawPose, attributes.cur_pose, attributes.map_scan_pose]",
            source,
        )
        renderer = (ROOT / "custom_components" / "anthbot_map" / "frontend" / "renderer.js").read_text(encoding="utf-8")
        heading_block = renderer.split("const headingCandidates = [", 1)[1].split("];", 1)[0]
        yaw_block = renderer.split("const yawCandidates = [", 1)[1].split("];", 1)[0]
        self.assertLess(heading_block.index("raw_pose"), heading_block.index("cur_pose"))
        self.assertLess(yaw_block.index("raw_pose"), yaw_block.index("cur_pose"))

    def test_quarter_turn_map_fit_uses_swapped_viewport_axes(self) -> None:
        geometry = (ROOT / "custom_components" / "anthbot_map" / "frontend" / "geometry.js").read_text(encoding="utf-8")
        self.assertIn("const quarterTurn = Math.abs(Math.sin(rotation)) > Math.abs(Math.cos(rotation))", geometry)
        self.assertIn("const fitWidth = quarterTurn ? size.height : size.width", geometry)
        self.assertIn("const fitHeight = quarterTurn ? size.width : size.height", geometry)

    def test_pause_and_resume_services_are_registered(self) -> None:
        setup = INIT_SOURCE.read_text(encoding="utf-8")
        self.assertIn("SERVICE_PAUSE_MOW, _handle_pause_mow", setup)
        self.assertIn("SERVICE_RESUME_MOW, _handle_resume_mow", setup)

    def test_all_maintenance_reset_services_are_registered(self) -> None:
        setup = INIT_SOURCE.read_text(encoding="utf-8")
        for service, reset_id in (
            ("SERVICE_RESET_BLADE_MAINTENANCE", 1),
            ("SERVICE_RESET_CAMERA_MAINTENANCE", 2),
            ("SERVICE_RESET_DOCK_CONTACT_MAINTENANCE", 0),
        ):
            self.assertIn(service, setup)
            self.assertIn(f"_handle_reset_maintenance(service_call, {reset_id})", setup)
        self.assertIn('cmd="robot_maintenance_reset", data={"reset_id": reset_id}', setup)

    def test_last_task_is_persisted_across_home_assistant_restart(self) -> None:
        coordinator = COORDINATOR_SOURCE.read_text(encoding="utf-8")
        setup = INIT_SOURCE.read_text(encoding="utf-8")
        self.assertIn("Store[dict[str, Any]]", coordinator)
        self.assertIn("self._task_store.async_save(snapshot)", coordinator)
        self.assertIn("async def async_load_last_mowing_task", coordinator)
        self.assertIn("await coordinator.async_load_last_mowing_task()", setup)

    def test_no_task_message_exists_for_all_supported_languages(self) -> None:
        source = I18N_SOURCE.read_text(encoding="utf-8")
        block = source.split("const noTaskToResumeTranslations = {", 1)[1].split("};", 1)[0]
        for language in ("en", "hu", "de", "fr", "es", "it", "pt", "nl", "pl", "cs", "sk", "ro", "da", "sv", "no", "fi", "zh-CN", "zh-TW", "tr", "th", "vi", "ko", "km"):
            self.assertIn(f'{language}:', block.replace('"', ''))


if __name__ == "__main__":
    unittest.main()
