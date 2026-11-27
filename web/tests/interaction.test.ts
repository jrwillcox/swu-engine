import { describe, expect, it } from "vitest";
import {
  BASE_TARGET,
  buildInteraction,
  directActions,
  subjectOf,
  targetOf,
  targetsForSubject,
  upgradeHosts,
} from "../src/game/interaction";
import { action, card } from "./fixtures";

describe("interaction mapping", () => {
  it("anchors a PlayCard to its hand card as subject, no target", () => {
    const a = action("PlayCard", { instance_id: "h1", upgrade_target_id: null });
    expect(subjectOf(a)).toBe("h1");
    expect(targetOf(a)).toBeUndefined();
  });

  it("treats an upgrade PlayCard's host as the target", () => {
    const a = action("PlayCard", { instance_id: "u1", upgrade_target_id: "host9" });
    expect(subjectOf(a)).toBe("u1");
    expect(targetOf(a)).toBe("host9");
  });

  it("anchors a SmugglePlay to its resource card as subject, no target", () => {
    const a = action("SmugglePlay", { instance_id: "r1", upgrade_target_id: null });
    expect(subjectOf(a)).toBe("r1");
    expect(targetOf(a)).toBeUndefined();
  });

  it("treats a smuggled upgrade's host as the target", () => {
    const a = action("SmugglePlay", { instance_id: "r2", upgrade_target_id: "host9" });
    expect(subjectOf(a)).toBe("r2");
    expect(targetOf(a)).toBe("host9");
  });

  it("makes a smuggleable resource a clickable subject", () => {
    const inter = buildInteraction([
      action("Pass", {}, "a0"),
      action("SmugglePlay", { instance_id: "r1", upgrade_target_id: null }, "a1"),
    ]);
    expect(inter.subjects.has("r1")).toBe(true);
    expect(inter.controls.map((c) => c.kind)).toContain("Pass");
  });

  it("maps an attack on base to BASE and on a unit to its id", () => {
    const base = action("AttackWithUnit", { attacker_id: "g1", defender_id: null });
    const unit = action("AttackWithUnit", { attacker_id: "g1", defender_id: "e2" });
    expect(targetOf(base)).toBe(BASE_TARGET);
    expect(targetOf(unit)).toBe("e2");
  });

  it("separates controls from card-anchored actions", () => {
    const inter = buildInteraction([
      action("Pass", {}, "a0"),
      action("PlayCard", { instance_id: "h1" }, "a1"),
      action("AttackWithUnit", { attacker_id: "g1", defender_id: "e2" }, "a2"),
      action("DeployLeader", {}, "a3"),
    ]);
    expect(inter.subjects.has("h1")).toBe(true);
    expect(inter.subjects.has("g1")).toBe(true);
    // Pass and DeployLeader are flow controls.
    const controlKinds = inter.controls.map((c) => c.kind);
    expect(controlKinds).toContain("Pass");
    expect(controlKinds).toContain("DeployLeader");
  });

  it("collects multiple attack targets for one attacker", () => {
    const inter = buildInteraction([
      action("AttackWithUnit", { attacker_id: "g1", defender_id: null }, "a0"),
      action("AttackWithUnit", { attacker_id: "g1", defender_id: "e1" }, "a1"),
      action("AttackWithUnit", { attacker_id: "g1", defender_id: "e2" }, "a2"),
    ]);
    const targets = targetsForSubject(inter, "g1");
    expect(targets.size).toBe(3);
    expect(targets.has(BASE_TARGET)).toBe(true);
    expect(directActions(inter, "g1")).toHaveLength(0);
  });

  it("offers an attached upgrade's own action on its host card", () => {
    // Bacta Tank's Action is anchored to the upgrade, which is only a chip on the
    // base: without the host map nothing on the board could be clicked to use it.
    const use = action("UseAbility", { source_id: "up1", ability_idx: 1, actor_id: null }, "a0");
    expect(buildInteraction([use]).subjects.has("base1")).toBe(false);
    const inter = buildInteraction([use], new Map([["up1", "base1"]]));
    expect(inter.subjects.has("base1")).toBe(true);
    expect(inter.subjects.has("up1")).toBe(false);
    expect(directActions(inter, "base1")).toEqual([use]);
  });

  it("maps each attached upgrade to its host", () => {
    const host = card({
      instance_id: "base1",
      attached_upgrades: [card({ instance_id: "up1" }), card({ instance_id: "up2" })],
    });
    const hosts = upgradeHosts([host, card({ instance_id: "u9" })]);
    expect(hosts.get("up1")).toBe("base1");
    expect(hosts.get("up2")).toBe("base1");
    expect(hosts.has("u9")).toBe(false);
  });

  it("surfaces ChooseTarget options as free targets", () => {
    const inter = buildInteraction([
      action("ChooseTarget", { target_id: "x1" }, "a0"),
      action("ChooseTarget", { target_id: "x2" }, "a1"),
    ]);
    expect(inter.freeTargets.has("x1")).toBe(true);
    expect(inter.freeTargets.has("x2")).toBe(true);
  });
});
