import { checkSkill } from "./lib/skill.mjs";

checkSkill("change-spec", [
  'Run openspec validate <slug> --strict --no-interactive from ~/specs/<project> until it prints "is valid".',
  "Each requirement MUST include at least one #### Scenario: block.",
  "Stop and ask the user to approve the spec before planning.",
  "When execution shows the spec is wrong, stop dispatching, amend the delta, validate again, ask the user, then re-plan only the remaining tasks.",
  "Set OPENSPEC_TELEMETRY=0.",
]);
