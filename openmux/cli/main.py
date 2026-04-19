"""
Command-line interface for OpenMux.
"""

import sys
import os
from pathlib import Path
from typing import Optional

try:
    import typer
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.table import Table
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    typer = None

from ..core.orchestrator import Orchestrator
from ..classifier.task_types import TaskType
import json
import datetime

# History storage
_HISTORY_DIR = Path.home() / ".openmux"
_HISTORY_FILE = _HISTORY_DIR / "history.jsonl"


def _ensure_history_dir():
    try:
        _HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Best-effort: if we cannot create directory, silently skip history
        return False
    return True


def _append_history_entry(user_input: str, response: str, provider: str = ""):
    if not _ensure_history_dir():
        return

    entry = {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "query": user_input,
        "response": response,
        "provider": provider
    }

    try:
        with open(_HISTORY_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        # Don't let history failures affect CLI
        pass


if RICH_AVAILABLE:
    app = typer.Typer(
        name="openmux",
        help="OpenMux - Free Multi-Source GenAI Orchestration",
        add_completion=False
    )
    console = Console()
else:
    app = None
    console = None


def version_callback(value: bool):
    """Display version information."""
    if value:
        from .. import __version__
        if RICH_AVAILABLE:
            console.print(f"OpenCascade version {__version__}")
        else:
            print(f"OpenCascade version {__version__}")
        raise typer.Exit()


if RICH_AVAILABLE:
    @app.command()
    def chat(
        query: Optional[str] = typer.Argument(None, help="Query to process"),
        task_type: Optional[str] = typer.Option(None, "--task", "-t", help="Task type (chat, code, embeddings)"),
        interactive: bool = typer.Option(False, "--interactive", "-i", help="Start interactive chat mode"),
        stream: bool = typer.Option(False, "--stream", "-s", help="Stream output as it arrives"),
    ):
        """Chat with AI models using OpenMux."""
        try:
            # Initialize orchestrator with context manager
            with Orchestrator() as orchestrator:
            
                if interactive or not query:
                    # Interactive mode
                    console.print(Panel(
                        "[bold cyan]OpenMux Interactive Chat[/bold cyan]\n"
                        "Type your questions below. Type 'exit' or 'quit' to end the session.",
                        style="cyan"
                    ))
                    
                    while True:
                        try:
                            user_input = Prompt.ask("\n[bold green]You[/bold green]")
                            
                            if user_input.lower() in ['exit', 'quit', 'q']:
                                console.print("[yellow]Goodbye![/yellow]")
                                break
                            
                            if not user_input.strip():
                                continue
                            
                            # Parse task type
                            task = None
                            if task_type:
                                task = TaskType.from_string(task_type)
                            
                            # Process query
                            console.print("[dim]Processing...[/dim]")
                            # Support streaming if provider/Orchestrator supports it
                            if stream:
                                # orchestrator.process_stream returns an async iterator
                                import asyncio

                                async def _stream_and_print():
                                    try:
                                        full = []
                                        async for chunk in orchestrator.process_stream(user_input, task_type=task):
                                            console.print(chunk)
                                            full.append(chunk)
                                        # Save assembled response to history
                                        try:
                                            _append_history_entry(user_input, "\n".join(full))
                                        except Exception:
                                            pass
                                    except Exception as e:
                                        console.print(f"[red]Stream error: {e}[/red]")

                                asyncio.run(_stream_and_print())
                            else:
                                response = orchestrator.process(query=user_input, task_type=task)
                                # Display response
                                console.print(Panel(
                                    response,
                                    title="[bold blue]AI Response[/bold blue]",
                                    style="blue"
                                ))
                                # Append to history
                                try:
                                    _append_history_entry(user_input, response)
                                except Exception:
                                    pass
                            
                        except KeyboardInterrupt:
                            console.print("\n[yellow]Goodbye![/yellow]")
                            break
                        except Exception as e:
                            console.print(f"[red]Error: {str(e)}[/red]")
                else:
                    # Single query mode
                    task = None
                    if task_type:
                        task = TaskType.from_string(task_type)
                    
                    console.print("[dim]Processing...[/dim]")
                    if stream:
                        import asyncio

                        async def _stream_and_print():
                            full = []
                            async for chunk in orchestrator.process_stream(query, task_type=task):
                                console.print(chunk)
                                full.append(chunk)
                            try:
                                _append_history_entry(query, "\n".join(full))
                            except Exception:
                                pass

                        asyncio.run(_stream_and_print())
                    else:
                        response = orchestrator.process(query=query, task_type=task)
                        console.print(Panel(
                            response,
                            title="[bold blue]Response[/bold blue]",
                            style="blue"
                        ))
                        try:
                            _append_history_entry(query, response)
                        except Exception:
                            pass
                
        except Exception as e:
            console.print(Panel(f"[bold red]Error:[/bold red] {str(e)}", style="red"))
            raise typer.Exit(code=1)


    @app.command()
    def init(
        force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing .env file")
    ):
        """Initialize OpenMux configuration with API keys."""
        try:
            env_path = Path.cwd() / ".env"
            env_example_path = Path(__file__).parent.parent.parent / ".env.example"
            
            # Check if .env exists
            if env_path.exists() and not force:
                if not Confirm.ask(f".env file already exists at {env_path}. Overwrite?"):
                    console.print("[yellow]Initialization cancelled.[/yellow]")
                    raise typer.Exit()
            
            console.print(Panel(
                "[bold cyan]OpenMux Setup Wizard[/bold cyan]\n\n"
                "This wizard will help you configure OpenMux with your API keys.\n"
                "You can press Enter to skip optional keys.",
                style="cyan"
            ))
            
            # Collect API keys
            console.print("\n[bold]Required API Keys:[/bold]")
            openrouter_key = Prompt.ask(
                "OpenRouter API Key (get it at https://openrouter.ai/keys)",
                default=""
            )
            
            console.print("\n[bold]Optional API Keys:[/bold]")
            hf_token = Prompt.ask(
                "HuggingFace Token (optional, press Enter to skip)",
                default=""
            )
            
            ollama_url = Prompt.ask(
                "Ollama URL (for local models)",
                default="http://localhost:11434"
            )
            
            # Write .env file
            env_content = "# OpenMux Environment Variables\n"
            env_content += "# Generated by openmux init\n\n"
            
            env_content += "# =====================================\n"
            env_content += "# Provider API Keys\n"
            env_content += "# =====================================\n\n"
            
            env_content += "# OpenRouter API Key (Required)\n"
            env_content += f"OPENROUTER_API_KEY={openrouter_key}\n\n"
            
            if hf_token:
                env_content += "# HuggingFace Token (Optional)\n"
                env_content += f"HF_TOKEN={hf_token}\n\n"
            
            env_content += "# =====================================\n"
            env_content += "# Ollama Configuration (Optional)\n"
            env_content += "# =====================================\n\n"
            env_content += f"OLLAMA_URL={ollama_url}\n"
            
            # Write to file
            with open(env_path, 'w') as f:
                f.write(env_content)
            
            console.print(Panel(
                f"[bold green]✓ Configuration saved to {env_path}[/bold green]\n\n"
                "You can now use OpenMux:\n"
                "  • openmux chat \"Hello!\"\n"
                "  • openmux chat --interactive",
                style="green"
            ))
            
        except Exception as e:
            console.print(Panel(f"[bold red]Error:[/bold red] {str(e)}", style="red"))
            raise typer.Exit(code=1)


    @app.command()
    def query(
        text: str = typer.Argument(..., help="Query text to process"),
        task_type: Optional[str] = typer.Option(None, "--task", "-t", help="Task type (chat, code, embeddings)"),
        num_models: int = typer.Option(1, "--models", "-m", help="Number of models to use"),
        combination: str = typer.Option("merge", "--combine", "-c", help="Combination method (merge, summarize)"),
        version: Optional[bool] = typer.Option(None, "--version", "-v", callback=version_callback, is_eager=True)
    ):
        """Process a query using OpenCascade."""
        try:
            # Initialize orchestrator
            orchestrator = Orchestrator()
            
            # Parse task type
            task = None
            if task_type:
                task = TaskType.from_string(task_type)
            
            # Process query
            console.print(Panel("Processing query...", style="blue"))
            
            if num_models > 1:
                response = orchestrator.process_multi(
                    query=text,
                    num_models=num_models,
                    combination_method=combination,
                    task_type=task
                )
            else:
                response = orchestrator.process(
                    query=text,
                    task_type=task
                )
            
            # Display response
            console.print(Panel(response, title="Response", style="green"))
            
        except Exception as e:
            console.print(Panel(f"Error: {str(e)}", style="red"))
            raise typer.Exit(code=1)


    @app.command()
    def providers():
        """List available providers."""
        try:
            orchestrator = Orchestrator()
            orchestrator._initialize_selector()
            
            available = orchestrator.registry.get_all()
            
            console.print(Panel("Available Providers", style="blue"))
            
            for name, provider in available.items():
                status = "✓" if provider.is_available() else "✗"
                console.print(f"{status} {name}: {provider.name}")
            
        except Exception as e:
            console.print(Panel(f"Error: {str(e)}", style="red"))
            raise typer.Exit(code=1)


def main():
    """Main CLI entry point."""
    if not RICH_AVAILABLE:
        print("Error: CLI requires 'typer' and 'rich' packages.")
        print("Install with: pip install typer rich")
        sys.exit(1)
    
    app()


if RICH_AVAILABLE:
    @app.command()
    def history(
        show: bool = typer.Option(True, "--show/--no-show", help="Show recent history entries"),
        export: Optional[Path] = typer.Option(None, "--export", "-e", help="Export history to a file (JSONL)"),
        limit: int = typer.Option(20, "--limit", "-n", help="Number of entries to show")
    ):
        """Show or export local session history."""
        try:
            if export:
                # Copy history file to export path
                if not _HISTORY_FILE.exists():
                    console.print("[yellow]No history to export.[/yellow]")
                    raise typer.Exit()
                with open(_HISTORY_FILE, 'r', encoding='utf-8') as src, open(export, 'w', encoding='utf-8') as dst:
                    for line in src:
                        dst.write(line)
                console.print(f"[green]Exported history to {export}[/green]")
                raise typer.Exit()

            if show:
                if not _HISTORY_FILE.exists():
                    console.print("[yellow]No history available.[/yellow]")
                    raise typer.Exit()

                entries = []
                with open(_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            entries.append(json.loads(line))
                        except Exception:
                            continue

                # Show most recent by timestamp
                entries = sorted(entries, key=lambda e: e.get('timestamp', ''), reverse=True)[:limit]

                table = Table(title="OpenMux History")
                table.add_column("When")
                table.add_column("Query")
                table.add_column("Provider")
                table.add_column("Response (truncated)")

                for e in entries:
                    when = e.get('timestamp', '')
                    q = (e.get('query') or '')[:60]
                    p = e.get('provider') or ''
                    r = (e.get('response') or '')[:120].replace('\n', ' ')
                    table.add_row(when, q, p, r)

                console.print(table)
                raise typer.Exit()

        except Exception as e:
            console.print(Panel(f"[bold red]Error:[/bold red] {str(e)}", style="red"))
            raise typer.Exit(code=1)


if __name__ == "__main__":
    main()
