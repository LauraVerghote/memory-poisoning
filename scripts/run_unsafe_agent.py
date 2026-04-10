"""Interactive runner for the unsafe agent (Lab 1 & 2)."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console
from rich.panel import Panel
from src.agent_unsafe.agent import UnsafeAgent

console = Console()


def main():
    console.print(
        Panel(
            "[bold red]UNSAFE AGENT[/bold red] — No memory protection\n"
            "Type 'quit' to exit, 'memories' to inspect stored memories, "
            "'clear' to reset memory.",
            title="Memory Poisoning Workshop",
            style="red",
        )
    )

    agent = UnsafeAgent()

    while True:
        try:
            user_input = console.input("\n[bold green]You:[/] ")
        except (EOFError, KeyboardInterrupt):
            break

        if user_input.strip().lower() == "quit":
            break
        elif user_input.strip().lower() == "memories":
            memories = agent.memory.get_all()
            if memories:
                for m in memories:
                    console.print(
                        f"  [dim]#{m['id']}[/] [{m['source']}] {m['content']}"
                    )
            else:
                console.print("  [dim]No memories stored.[/]")
            continue
        elif user_input.strip().lower() == "clear":
            agent.memory.clear()
            agent.conversation = []
            console.print("  [dim]Memory cleared.[/]")
            continue

        response = agent.chat(user_input)
        console.print(f"\n[bold blue]Agent:[/] {response}")


if __name__ == "__main__":
    main()
