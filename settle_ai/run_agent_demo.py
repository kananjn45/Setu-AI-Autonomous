"""
SETTLE.AI - Interactive Live Terminal Demo Runner (Dev 1 Brain)
Showcases autonomous dispute resolution, streaming LangGraph execution,
and Human-in-the-Loop circuit breakers with rich terminal output.
"""

import os
import sys

# Ensure UTF-8 output on Windows consoles to prevent charmap UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure workspace root is in sys.path
workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

# Auto-delegate to .venv python if executed via unconfigured global python
venv_python = os.path.join(workspace_root, ".venv", "Scripts", "python.exe")
if sys.prefix == sys.base_prefix and os.path.exists(venv_python) and os.path.abspath(sys.executable) != os.path.abspath(venv_python):
    import subprocess
    sys.exit(subprocess.call([venv_python] + sys.argv))

import time
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from settle_ai.agent.schemas import (
    DisputeGrievance,
    DisputeChannel,
)
from settle_ai.agent.orchestrator import orchestrator
from settle_ai.agent.tools import reset_sandbox_state
from settle_ai.voice.tts_service import tts_synthesizer
from settle_ai.voice.nlu_extractor import nlu_extractor

console = Console()


def display_header():
    console.print(
        Panel.fit(
            "[bold cyan]SETU — Autonomous Operations Teammate (Team: 0 and 1)[/bold cyan]\n"
            "[yellow]Paytm Build for India Hackathon | Track 3: Autonomous AI Teammates[/yellow]\n"
            "[white]Zero-touch dispute adjudication, Soundbox triage & multi-system ledger resolution[/white]",
            border_style="cyan",
        )
    )


def run_interactive_demo():
    display_header()
    reset_sandbox_state()

    console.print("\n[bold]Select a Live Simulation Scenario:[/bold]")
    console.print("  [1] [green]Scenario 1:[/green] Standard Drop (INR 350) — Autonomous Settle & Soundbox Chirp (<30s)")
    console.print("  [2] [bold magenta]Scenario 2:[/bold magenta] Safety Circuit Breaker (INR 15,000) — High-Value HITL Halt & Resume")
    console.print("  [3] [yellow]Scenario 3:[/yellow] Auto-Reversal Pending (INR 420) — Provisional Settlement")
    console.print("  [4] [blue]Scenario 4:[/blue] Real-Time Streaming Generator (WebSocket Emulation)")
    console.print("  [5] [bold magenta]Scenario 5 (Sarvam AI Voice & NLU):[/bold magenta] Custom Hindi Grievance -> Sarvam NLU -> Settle -> Sarvam Bulbul TTS Chirp")

    choice = input("\nEnter choice [1-5] (default 1): ").strip() or "1"

    if choice == "5":
        default_phrase = "Bhaiya humari dukan pe 350 rupaye kata par Soundbox nahi bola. RRN number hai 410294820192"
        console.print(f"\n[italic cyan]Enter Hindi voice transcript (or press Enter for default):[/italic cyan]")
        user_input = input(f"Transcript: ").strip() or default_phrase
        
        console.print("\n[bold cyan]>>> Parsing Hindi Speech with Sarvam-105B NLU...[/bold cyan]")
        extracted = nlu_extractor.extract_grievance_entities(user_input)
        console.print(f"  • Extracted RRN: [bold yellow]{extracted['rrn']}[/bold yellow]")
        console.print(f"  • Extracted Amount: [bold yellow]INR {extracted['amount']:,.2f}[/bold yellow]")
        console.print(f"  • Intent: [bold green]{extracted['intent']}[/bold green] (via {extracted['source']})")
        
        grievance = DisputeGrievance(
            dispute_id="DSP_SARVAM_LIVE",
            merchant_id="MERCH_GUPTA_TEA",
            device_id="SB_DELHI_0841",
            rrn=extracted["rrn"],
            amount=extracted["amount"],
            voice_transcript=user_input,
            channel=DisputeChannel.INDIC_VOICE,
            merchant_name="Gupta Tea Stall",
            merchant_phone="+919811223344",
        )
    elif choice == "1":
        grievance = DisputeGrievance(
            dispute_id="DSP_LIVE_001",
            merchant_id="MERCH_GUPTA_TEA",
            device_id="SB_DELHI_0841",
            rrn="410294820192",
            amount=350.0,
            voice_transcript="Bhaiya 350 rupaye kata par Soundbox nahi bola",
            channel=DisputeChannel.INDIC_VOICE,
            merchant_name="Gupta Tea Stall",
            merchant_phone="+919811223344",
        )
    elif choice == "2":
        grievance = DisputeGrievance(
            dispute_id="DSP_LIVE_002",
            merchant_id="MERCH_SHARMA_KIRANA",
            device_id="SB_DELHI_0841",
            rrn="883920194821",
            amount=15000.0,
            voice_transcript="Order ka 15,000 nahi aaya hai",
            channel=DisputeChannel.INDIC_VOICE,
            merchant_name="Sharma Kirana Store",
            merchant_phone="+919822334455",
        )
    elif choice == "3":
        grievance = DisputeGrievance(
            dispute_id="DSP_LIVE_003",
            merchant_id="MERCH_GUPTA_TEA",
            device_id="SB_DELHI_0841",
            rrn="772910394812",
            amount=420.0,
            voice_transcript="Customer bol raha hai paise kat gaye",
            channel=DisputeChannel.WHATSAPP,
            merchant_name="Gupta Tea Stall",
        )
    else:
        grievance = DisputeGrievance(
            dispute_id="DSP_LIVE_004_STREAM",
            merchant_id="MERCH_SHARMA_KIRANA",
            device_id="SB_DELHI_0841",
            rrn="982174019284",
            amount=500.0,
            channel=DisputeChannel.INDIC_VOICE,
            merchant_name="Sharma Kirana Store",
        )

    console.print(f"\n[bold green]>>> Ingesting Merchant Grievance [{grievance.dispute_id}]...[/bold green]")
    console.print(f"  • Merchant: [bold]{grievance.merchant_name}[/bold] | Device: {grievance.device_id}")
    console.print(f"  • Claimed Amount: [bold yellow]INR {grievance.amount:,.2f}[/bold yellow] | RRN: {grievance.rrn}")
    if grievance.voice_transcript:
        console.print(f"  • Voice Transcript: [italic]\"{grievance.voice_transcript}\"[/italic]")

    console.print("\n[bold cyan]>>> Executing LangGraph Cyclic Diagnostic Graph...[/bold cyan]\n")

    table = Table(title="SETTLE.AI Diagnostic Execution Trace", border_style="dim")
    table.add_column("Step", justify="center", style="bold")
    table.add_column("Agent Node", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Latency", justify="right", style="yellow")
    table.add_column("Telemetry & Summary", style="white")

    # Stream real-time node executions
    halted_state = None
    for event in orchestrator.stream_dispute_resolution(grievance):
        if event.get("event_type") == "NODE_EXECUTED":
            step = event.get("latest_step", {})
            status_text = Text(step.get("status", "DONE"))
            if step.get("status") == "COMPLETED":
                status_text.stylize("bold green")
            elif "HALT" in step.get("status"):
                status_text.stylize("bold red")

            summary_clean = event.get("step_summary", "").replace("\u20b9", "INR ")
            table.add_row(
                str(step.get("step_id", "-")),
                event.get("node_name", ""),
                status_text,
                f"{event.get('latency_ms', 0):.1f}ms",
                summary_clean,
            )
        elif event.get("event_type") == "WORKFLOW_HALTED":
            halted_state = orchestrator.get_dispute(grievance.dispute_id)

    console.print(table)

    final_state = orchestrator.get_dispute(grievance.dispute_id)

    if final_state and final_state.hitl_required and not final_state.hitl_approved:
        clean_halt_reason = final_state.hitl_reason.replace("\u20b9", "INR ")
        console.print(
            Panel(
                f"[bold red]CIRCUIT BREAKER ENGAGED — AUTONOMOUS WRITE HALTED[/bold red]\n\n"
                f"Reason: {clean_halt_reason}\n"
                f"Confidence Score: [bold yellow]{final_state.confidence_score:.1%}[/bold yellow]\n"
                f"Bank Switch Status: [bold]{final_state.bank_status.value}[/bold]\n"
                f"Soundbox Telemetry: [bold]{final_state.soundbox_status.value} (RSSI: {final_state.soundbox_telemetry.rssi_dbm} dBm)[/bold]\n\n"
                f"[bold cyan]Simulating Human Supervisor Review Desk...[/bold cyan]",
                title="HITL Operational Gateway",
                border_style="red",
            )
        )
        signoff = input("\n[Supervisor] Approve this transaction for settlement? (y/n): ").strip().lower()
        if signoff in ("y", "yes", ""):
            console.print("\n[bold green]>>> Supervisor Approved: Resuming LangGraph Execution DAG...[/bold green]")
            resumed_state = orchestrator.approve_hitl(
                dispute_id=grievance.dispute_id,
                supervisor_notes="Approved via terminal supervisor console after reviewing bank logs.",
            )
            clean_res_msg = resumed_state.final_resolution_message.replace("\u20b9", "INR ")
            console.print(Panel(f"[bold green]{clean_res_msg}[/bold green]", title="Resolution Finalized", border_style="green"))
        else:
            console.print("[yellow]Dispute held in supervisor review queue.[/yellow]")
    else:
        # Synthesize official Sarvam Bulbul TTS Soundbox audio
        chirp_path = os.path.join(workspace_root, "settle_ai", "static", "audio", f"chirp_{final_state.rrn}.wav")
        chirp_data = tts_synthesizer.synthesize_chirp(amount=final_state.amount, output_file_path=chirp_path)

        clean_res_msg = final_state.final_resolution_message.replace("\u20b9", "INR ")
        console.print(
            Panel(
                f"[bold green]AUTONOMOUS RESOLUTION ACCOMPLISHED[/bold green]\n\n"
                f"{clean_res_msg}\n\n"
                f"• Soundbox MQTT Payload Pushed: [bold]{final_state.soundbox_pushed}[/bold]\n"
                f"• Ledger Credited (Idempotent): [bold]{final_state.ledger_credited}[/bold]\n"
                f"• WhatsApp Notification: [bold]{final_state.notification_dispatched}[/bold]\n"
                f"• [bold cyan]Sarvam Bulbul TTS Audio Chirp:[/bold cyan] [bold yellow]\"{chirp_data['text']}\"[/bold yellow]\n"
                f"  Saved to: [dim]{chirp_path}[/dim] ({chirp_data['byte_size']:,} bytes)",
                title="SETTLE.AI Autonomous Teammate Result",
                border_style="green",
            )
        )


if __name__ == "__main__":
    run_interactive_demo()
