"""Interactive runner for the safe (hardened) agent (Lab 3)."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console
from rich.panel import Panel
from src.agent_safe.agent import SafeAgent

console = Console()


def main():
    console.print(
        Panel(
            "[bold green]SAFE AGENT[/bold green] — Memory protection enabled\n"
            "Type 'quit' to exit, 'memories' to inspect, 'pending' to see "
            "queued memories,\n'approve N' to approve, 'reject N' to reject, "
            "'versions' for history, 'wait' to flush writes, 'clear' to reset.",
            title="Memory Poisoning Workshop",
            style="green",
        )
    )

    agent = SafeAgent()

    while True:
        try:
            user_input = console.input("\n[bold green]You:[/] ")
        except (EOFError, KeyboardInterrupt):
            break

        cmd = user_input.strip().lower()

        if cmd == "quit":
            break
        elif cmd == "memories":
            memories = agent.memory.get_all()
            if memories:
                for m in memories:
                    console.print(f"  [dim]{m['id'][:8]}[/] {m['content']}")
            else:
                console.print("  [dim]No memories stored.[/]")
            continue
        elif cmd == "pending":
            pending = agent.list_pending()
            if pending:
                for i, p in enumerate(pending):
                    console.print(f"  [yellow]#{i}[/] {p['content']}")
            else:
                console.print("  [dim]No pending memories.[/]")
            continue
        elif cmd.startswith("approve "):
            try:
                idx = int(cmd.split(" ", 1)[1])
                result = agent.approve_memory(idx)
                console.print(f"  {result}")
            except (ValueError, IndexError):
                console.print("  [red]Usage: approve <index>[/]")
            continue
        elif cmd.startswith("reject "):
            try:
                idx = int(cmd.split(" ", 1)[1])
                result = agent.reject_memory(idx)
                console.print(f"  {result}")
            except (ValueError, IndexError):
                console.print("  [red]Usage: reject <index>[/]")
            continue
        elif cmd == "versions":
            versions = agent.memory.get_versions()
            if versions:
                for v in versions:
                    console.print(
                        f"  v{v['version']} | {v['action'][:50]} | "
                        f"{v['timestamp']}"
                    )
            else:
                console.print("  [dim]No version history.[/]")
            continue
        elif cmd == "wait":
            console.print("  [dim]Waiting for pending memory updates...[/]")
            agent.memory.wait_for_pending()
            console.print("  [dim]Done.[/]")
            continue
        elif cmd == "clear":
            agent.memory.clear()
            agent.conversation = []
            console.print("  [dim]Memory cleared.[/]")
            continue

        response = agent.chat(user_input)
        console.print(f"\n[bold blue]Agent:[/] {response}")


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
