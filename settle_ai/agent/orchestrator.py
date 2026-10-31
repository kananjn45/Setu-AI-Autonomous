"""
SETTLE.AI - Agentic Orchestrator & Event Streaming Gateway
Coordinates dispute lifecycle, event streaming for WebSocket consumers,
and human-in-the-loop supervisor intervention.
"""

import logging
import warnings
from typing import Dict, Any, Generator, Optional, List
from langgraph.checkpoint.memory import MemorySaver

warnings.filterwarnings("ignore", message="Deserializing unregistered type")

from settle_ai.agent.schemas import (
    DisputeGrievance,
    AgentState,
    ResolutionAction,
)
from settle_ai.agent.state_graph import build_settle_agent_graph

logger = logging.getLogger("settle_ai.orchestrator")


class SettleOrchestrator:
    """Enterprise Orchestrator for SETTLE.AI Autonomous Teammate."""

    def __init__(self):
        self.checkpointer = MemorySaver()
        self.graph = build_settle_agent_graph(checkpointer=self.checkpointer)
        # In-memory registry for rapid dashboard access
        self.active_disputes: Dict[str, AgentState] = {}

    def _grievance_to_initial_state(self, grievance: DisputeGrievance) -> AgentState:
        """Converts incoming grievance model into LangGraph initial state."""
        return AgentState(
            dispute_id=grievance.dispute_id,
            merchant_id=grievance.merchant_id,
            device_id=grievance.device_id,
            rrn=grievance.rrn,
            amount=grievance.amount,
            voice_transcript=grievance.voice_transcript,
            channel=grievance.channel,
            merchant_name=grievance.merchant_name,
            merchant_phone=grievance.merchant_phone,
            customer_vpa=grievance.customer_vpa,
        )

    def resolve_dispute(self, grievance: DisputeGrievance) -> AgentState:
        """
        Executes end-to-end resolution synchronously.
        If circuit breaker trips, returns state halted at HITL escalation.
        """
        logger.info(f"[Orchestrator] Triggering resolution for dispute: {grievance.dispute_id}")
        initial_state = self._grievance_to_initial_state(grievance)
        config = {"configurable": {"thread_id": grievance.dispute_id}}

        # Invoke graph
        result_dict = self.graph.invoke(initial_state, config=config)
        final_state = AgentState(**result_dict) if isinstance(result_dict, dict) else result_dict
        self.active_disputes[grievance.dispute_id] = final_state
        return final_state

    def stream_dispute_resolution(self, grievance: DisputeGrievance) -> Generator[Dict[str, Any], None, AgentState]:
        """
        Generator that yields real-time node completion events for WebSocket / SSE streams.
        Ideal for Dev 4's Ops Control Room visualizer.
        """
        logger.info(f"[Orchestrator] Streaming resolution for dispute: {grievance.dispute_id}")
        initial_state = self._grievance_to_initial_state(grievance)
        config = {"configurable": {"thread_id": grievance.dispute_id}}

        last_state = initial_state
        for event in self.graph.stream(initial_state, config=config, stream_mode="updates"):
            for node_name, updated_fields in event.items():
                logger.info(f"[Stream] Node '{node_name}' finished execution.")
                
                # Fetch step log if present
                latest_step = None
                if "execution_steps" in updated_fields and updated_fields["execution_steps"]:
                    latest_step = updated_fields["execution_steps"][-1]
                    if hasattr(latest_step, "model_dump"):
                        latest_step = latest_step.model_dump()

                def _safe_serialize(val):
                    if hasattr(val, "model_dump"):
                        return val.model_dump()
                    if isinstance(val, (int, float, str, bool)) or val is None:
                        return val
                    if isinstance(val, dict):
                        return {k: _safe_serialize(v) for k, v in val.items()}
                    if isinstance(val, list):
                        return [_safe_serialize(v) for v in val]
                    return str(val)

                serialized_updates = {
                    k: _safe_serialize(v) for k, v in updated_fields.items() if k != "execution_steps"
                }

                yield {
                    "dispute_id": grievance.dispute_id,
                    "event_type": "NODE_EXECUTED",
                    "node_name": node_name,
                    "step_summary": latest_step["summary"] if latest_step else f"{node_name} completed",
                    "latency_ms": latest_step["latency_ms"] if latest_step else 0.0,
                    "state_updates": serialized_updates,
                    "latest_step": latest_step,
                }

        # Retrieve final checkpoint state
        snapshot = self.graph.get_state(config)
        final_state = AgentState(**snapshot.values)
        self.active_disputes[grievance.dispute_id] = final_state

        yield {
            "dispute_id": grievance.dispute_id,
            "event_type": "WORKFLOW_HALTED" if final_state.hitl_required and not final_state.hitl_approved else "WORKFLOW_COMPLETED",
            "is_completed": final_state.is_completed,
            "hitl_required": final_state.hitl_required,
            "final_message": final_state.final_resolution_message,
            "total_steps": len(final_state.execution_steps),
        }
        return final_state

    def approve_hitl(self, dispute_id: str, supervisor_notes: str = "Approved by Operations Lead") -> AgentState:
        """
        Resumes an escalated dispute with supervisor approval sign-off.
        Executes node_resume_hitl -> node_autonomous_settle -> END.
        """
        logger.info(f"[Orchestrator] Resuming HITL dispute {dispute_id} with supervisor sign-off")
        config = {"configurable": {"thread_id": dispute_id}}

        # Fetch paused checkpoint
        snapshot = self.graph.get_state(config)
        if not snapshot.values:
            raise ValueError(f"No checkpoint found for dispute_id: {dispute_id}")

        current_state = AgentState(**snapshot.values)
        current_state.hitl_approved = True
        current_state.hitl_supervisor_notes = supervisor_notes

        # Resume execution through the resume node
        resume_graph = build_settle_agent_graph(checkpointer=self.checkpointer)
        # Update checkpoint state
        self.graph.update_state(config, {
            "hitl_approved": True,
            "hitl_supervisor_notes": supervisor_notes,
        }, as_node="node_escalate_hitl")

        # Run remaining path starting from node_resume_hitl
        result = resume_graph.invoke(current_state, config=config)
        final_state = AgentState(**result) if isinstance(result, dict) else result
        self.active_disputes[dispute_id] = final_state
        return final_state

    def get_dispute(self, dispute_id: str) -> Optional[AgentState]:
        """Returns the current state of a dispute."""
        return self.active_disputes.get(dispute_id)

    def list_pending_hitl(self) -> List[AgentState]:
        """Lists all disputes waiting for human supervisor sign-off."""
        return [
            d for d in self.active_disputes.values()
            if d.hitl_required and not d.hitl_approved and not d.is_completed
        ]


# Default singleton orchestrator
orchestrator = SettleOrchestrator()
