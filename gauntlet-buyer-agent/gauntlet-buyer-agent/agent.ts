import { llmAgent, guildTools } from "@guildai/agents-sdk"
import { z } from "zod"

const GAUNTLET_API = process.env.GAUNTLET_API_URL ?? "http://127.0.0.1:8000"

export default llmAgent({
  description:
    "Hiring agent that vets worker agents via Gauntlet before committing to a hire. Calls the Gauntlet reliability endpoint, reads the report, and refuses any agent that failed the gauntlet.",
  tools: {
    ...guildTools,
    check_agent_reliability: {
      description:
        "Fetch the Gauntlet reliability report for a candidate agent. Returns the reliability score, probe verdicts, and hire/hold recommendation.",
      parameters: z.object({
        agent_id: z.string().describe("The agent ID to check, e.g. 'nimbus-proven' or 'nimbus-risk'"),
      }),
      execute: async ({ agent_id }: { agent_id: string }) => {
        const url = `${GAUNTLET_API}/agent/${agent_id}/reliability`
        try {
          const res = await fetch(url)
          if (res.status === 404) {
            return { error: "agent has not been vetted yet — run Gauntlet first", agent_id }
          }
          if (!res.ok) {
            return { error: `Gauntlet returned HTTP ${res.status}`, agent_id }
          }
          return await res.json()
        } catch (err) {
          return { error: `Could not reach Gauntlet at ${url}: ${err}`, agent_id }
        }
      },
    },
  },
  systemPrompt: `You are an autonomous hiring agent. Your job is to hire the best available worker agent for a task.

You do NOT trust marketing copy or self-reported claims. Before hiring any agent, you ALWAYS call check_agent_reliability to pull its Gauntlet report.

Your process:
1. The user will give you two candidate agent IDs.
2. Call check_agent_reliability for EACH candidate — do not skip this step.
3. Read each report out loud: state the reliability score, how many probes PROVEN / INCONSISTENT / FAILED, and the recommendation field.
4. If an agent has failed probes or a "hold" recommendation, refuse to hire it. State exactly why: which probes failed.
5. Hire the agent with the highest reliability score that has no FAILED probes.
6. Output your final decision in one sentence with the score as evidence.

Rules:
- Never hire an agent you have not checked with Gauntlet.
- Never hire an agent that FAILED any probe, regardless of score.
- If both agents fail, say so clearly — do not pick the lesser of two evils.
- Always show your reasoning before the final decision.
- Keep responses tight — this is a live demo.

Example final output:
"Hiring nimbus-proven (94% reliable, 8/8 probes passed). Refusing nimbus-risk — failed 3 safety probes. Decision is based on Gauntlet reliability data, not marketing."`,
  mode: "multi-turn",
})
