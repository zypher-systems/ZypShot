import subprocess
import re
import os
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys

console = Console()

def run_snapper_command(args):
    """Run a Snapper command and return its output."""
    try:
        result = subprocess.run(
            ["snapper"] + args,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error running snapper {args}: {e.stderr}[/red]")
        return None

def list_snapshots(config="root"):
    """List snapshots for the given config."""
    output = run_snapper_command(["--config", config, "list"])
    if not output:
        console.print("[yellow]No snapshots found or error in Snapper output[/yellow]")
        return []

    snapshots = []
    lines = output.splitlines()
    if len(lines) <= 2:  # No snapshots
        console.print("[yellow]No snapshots available[/yellow]")
        return []

    for line in lines[2:]:  # Skip header
        parts = [part.strip() for part in line.split("│")]
        if len(parts) >= 7:  # Expect at least 7 fields (up to Description)
            snapshot = {
                "number": parts[0] or "-",
                "type": parts[1] or "-",
                "date": parts[3] or "-",
                "description": parts[6] or "-"
            }
            snapshots.append(snapshot)
        else:
            console.print(f"[yellow]Skipping malformed line: {line}[/yellow]")
    
    return snapshots

def create_snapshot(config="root", description="Manual snapshot"):
    """Create a new snapshot."""
    output = run_snapper_command(["--config", config, "create", "--description", description])
    if output:
        console.print(f"[green]Snapshot created: {description}[/green]")

def delete_snapshot(config="root", number=""):
    """Delete a snapshot by number."""
    output = run_snapper_command(["--config", config, "delete", number])
    if output:
        console.print(f"[green]Snapshot {number} deleted[/green]")

def display_paginated_files(files, title, items_per_page=20):
    """Display a list of files with pagination."""
    if not files:
        console.print(f"[yellow]No {title.lower()} to display[/yellow]")
        return
    
    total_pages = (len(files) + items_per_page - 1) // items_per_page
    current_page = 1
    
    while True:
        console.clear()
        start_idx = (current_page - 1) * items_per_page
        end_idx = min(start_idx + items_per_page, len(files))
        
        table = Table(title=f"{title} (Page {current_page}/{total_pages})", show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=4)
        table.add_column("Path")
        
        for i, file_path in enumerate(files[start_idx:end_idx], start=start_idx + 1):
            table.add_row(str(i), file_path)
        
        console.print(table)
        console.print(f"\n[dim]Showing {start_idx + 1}-{end_idx} of {len(files)} files[/dim]")
        
        if total_pages > 1:
            console.print("\n[bold]Navigation:[/bold]")
            if current_page > 1:
                console.print("p - Previous page")
            if current_page < total_pages:
                console.print("n - Next page")
            console.print("q - Back to summary")
            
            choice = Prompt.ask("Enter choice", choices=["p", "n", "q"] if current_page > 1 and current_page < total_pages else 
                              (["n", "q"] if current_page == 1 else ["p", "q"]), default="q")
            
            if choice == "n" and current_page < total_pages:
                current_page += 1
            elif choice == "p" and current_page > 1:
                current_page -= 1
            elif choice == "q":
                break
        else:
            console.print("\nPress Enter to return to summary...")
            console.input()
            break

def compare_snapshots(config="root", num1="", num2=""):
    """Compare two snapshots and display changes in an organized way."""
    output = run_snapper_command(["--config", config, "status", f"{num1}..{num2}"])
    if not output:
        console.print(f"[yellow]No changes found or error occurred[/yellow]")
        return

    # Categorize changes
    added_files = []
    removed_files = []
    modified_files = []
    
    # Parse snapper status output (e.g., "+ /path", "- /path", "c /path", "  /path")
    for line in output.splitlines():
        line = line.strip()
        if line and re.match(r'^[+\-c ].+', line):  # Match status lines
            status, path = line[0], line[2:].strip()
            if status == '+':
                added_files.append(path)
            elif status == '-':
                removed_files.append(path)
            elif status == 'c':
                modified_files.append(path)

    # Display summary
    while True:
        console.clear()
        console.print(Panel(
            f"[green]Added: {len(added_files)} files[/green]\n"
            f"[red]Removed: {len(removed_files)} files[/red]\n"
            f"[yellow]Modified: {len(modified_files)} files[/yellow]\n"
            f"[cyan]Total changes: {len(added_files) + len(removed_files) + len(modified_files)} files[/cyan]",
            title=f"Snapshot Comparison Summary ({num1} → {num2})",
            border_style="blue"
        ))
        
        if not (added_files or removed_files or modified_files):
            console.print("[yellow]No changes to display[/yellow]")
            break
        
        console.print("\n[bold]View Details:[/bold]")
        options = []
        choices = []
        
        if added_files:
            options.append(f"1. View Added Files ({len(added_files)})")
            choices.append("1")
        if removed_files:
            options.append(f"2. View Removed Files ({len(removed_files)})")
            choices.append("2")
        if modified_files:
            options.append(f"3. View Modified Files ({len(modified_files)})")
            choices.append("3")
        
        options.append("4. Back to main menu")
        choices.append("4")
        
        for option in options:
            console.print(option)
        
        choice = Prompt.ask("Select an option", choices=choices, default="4")
        
        if choice == "1" and added_files:
            display_paginated_files(added_files, "Added Files")
        elif choice == "2" and removed_files:
            display_paginated_files(removed_files, "Removed Files")
        elif choice == "3" and modified_files:
            display_paginated_files(modified_files, "Modified Files")
        elif choice == "4":
            break

def rollback_guidance(config="root", number=""):
    """Display rollback instructions for a snapshot."""
    console.print(Panel(
        f"To rollback to snapshot {number}:\n"
        "1. Boot from an Arch Linux live USB.\n"
        "2. Mount your Btrfs partition: sudo mount /dev/sda1 /mnt\n"
        "3. Run: sudo snapper --config {config} rollback {number}\n"
        "4. Update GRUB: sudo arch-chroot /mnt; grub-mkconfig -o /boot/grub/grub.cfg\n"
        "5. Exit chroot (exit) and reboot.",
        title=f"Rollback Instructions for Snapshot {number}",
        border_style="yellow"
    ))

def snapshot_details(config="root", number=""):
    """Display detailed information for a snapshot."""
    output = run_snapper_command(["--config", config, "list"])
    if not output:
        console.print("[yellow]No snapshot details available[/yellow]")
        return

    lines = output.splitlines()
    for line in lines[2:]:  # Skip header
        parts = [part.strip() for part in line.split("│")]
        if len(parts) >= 7 and parts[0].strip() == str(number).strip():  # Robust number matching
            details = (
                f"Number: {parts[0]}\n"
                f"Type: {parts[1]}\n"
                f"Pre #: {parts[2]}\n"
                f"Date: {parts[3]}\n"
                f"User: {parts[4]}\n"
                f"Cleanup: {parts[5]}\n"
                f"Description: {parts[6]}\n"
                f"Userdata: {parts[7] if len(parts) > 7 else '-'}"
            )
            console.print(Panel(details, title=f"Snapshot {number} Details", border_style="green"))
            return
    console.print(f"[yellow]Snapshot {number} not found[/yellow]")

def cleanup_snapshots(config="root", cleanup_type="timeline"):
    """Trigger a snapshot cleanup."""
    output = run_snapper_command(["--config", config, "cleanup", cleanup_type])
    if output:
        console.print(f"[green]{cleanup_type} cleanup completed[/green]")
    else:
        console.print(f"[yellow]No snapshots cleaned or error occurred[/yellow]")

def view_cleanup_settings(config="root"):
    """Display cleanup settings from config file."""
    try:
        with open(f"/etc/snapper/configs/{config}", "r") as f:
            settings = f.read()
        cleanup_settings = "\n".join(line for line in settings.splitlines() if line.startswith(("TIMELINE_", "NUMBER_", "EMPTY_")))
        if cleanup_settings:
            console.print(Panel(cleanup_settings, title=f"Cleanup Settings for {config}", border_style="green"))
        else:
            console.print("[yellow]No cleanup settings found[/yellow]")
    except FileNotFoundError:
        console.print(f"[red]Config file /etc/snapper/configs/{config} not found[/red]")

def edit_cleanup_settings(config="root"):
    """Edit cleanup settings in config file."""
    valid_settings = [
        "TIMELINE_CREATE", "TIMELINE_CLEANUP", "TIMELINE_MIN_AGE", "TIMELINE_LIMIT_HOURLY",
        "TIMELINE_LIMIT_DAILY", "TIMELINE_LIMIT_WEEKLY", "TIMELINE_LIMIT_MONTHLY", "TIMELINE_LIMIT_YEARLY",
        "NUMBER_CLEANUP", "NUMBER_MIN_AGE", "NUMBER_LIMIT",
        "EMPTY_PRE_POST_CLEANUP", "EMPTY_PRE_POST_MIN_AGE"
    ]
    console.print("\nAvailable settings to edit:")
    for setting in valid_settings:
        console.print(f"- {setting}")
    
    setting = Prompt.ask("Enter setting to edit", default="TIMELINE_LIMIT_HOURLY")
    if setting not in valid_settings:
        console.print(f"[red]Invalid setting: {setting}[/red]")
        return

    value = Prompt.ask(f"Enter new value for {setting}")
    try:
        # Validate numeric settings
        if setting in ["TIMELINE_MIN_AGE", "TIMELINE_LIMIT_HOURLY", "TIMELINE_LIMIT_DAILY",
                       "TIMELINE_LIMIT_WEEKLY", "TIMELINE_LIMIT_MONTHLY", "TIMELINE_LIMIT_YEARLY",
                       "NUMBER_MIN_AGE", "NUMBER_LIMIT", "EMPTY_PRE_POST_MIN_AGE"]:
            value = str(int(value))  # Ensure integer
        elif setting in ["TIMELINE_CREATE", "TIMELINE_CLEANUP", "NUMBER_CLEANUP", "EMPTY_PRE_POST_CLEANUP"]:
            if value.lower() not in ["yes", "no"]:
                console.print(f"[red]Value must be 'yes' or 'no' for {setting}[/red]")
                return

        # Read and update config file
        config_file = f"/etc/snapper/configs/{config}"
        try:
            with open(config_file, "r") as f:
                lines = f.readlines()
            with open(config_file, "w") as f:
                found = False
                for line in lines:
                    if line.startswith(f"{setting}="):
                        f.write(f"{setting}=\"{value}\"\n")
                        found = True
                    else:
                        f.write(line)
                if not found:
                    f.write(f"{setting}=\"{value}\"\n")
            # Ensure correct permissions
            os.chmod(config_file, 0o644)
            console.print(f"[green]Updated {setting} to {value} in {config_file}[/green]")
        except PermissionError:
            console.print(f"[red]Permission denied: Run as root to edit {config_file}[/red]")
        except FileNotFoundError:
            console.print(f"[red]Config file {config_file} not found[/red]")
    except ValueError:
        console.print(f"[red]Invalid value for {setting}: Must be a number[/red]")

def display_snapshots(snapshots):
    """Display snapshots in a table."""
    table = Table(title="Snapper Snapshots", show_header=True, header_style="bold magenta")
    table.add_column("Number", style="cyan")
    table.add_column("Type")
    table.add_column("Date")
    table.add_column("Description")
    
    for snapshot in snapshots:
        table.add_row(
            snapshot["number"],
            snapshot["type"],
            snapshot["date"],
            snapshot["description"]
        )
    
    console.print(table)

def select_snapshot(snapshots, prompt_message="Select a snapshot"):
    """Allow interactive snapshot selection using prompt_toolkit."""
    snapshot_numbers = [s["number"] for s in snapshots]
    completer = WordCompleter(snapshot_numbers)
    bindings = KeyBindings()
    
    @bindings.add(Keys.ControlC)
    def _(event):
        event.app.exit(result=None)
    
    session = PromptSession(prompt_message + ": ", completer=completer, key_bindings=bindings)
    return session.prompt()

def main_menu():
    """Display the main menu and handle user input."""
    config = "root"
    while True:
        console.clear()
        console.print(Panel("[bold cyan]ZypShot - Snapshot Management[/bold cyan]\n[dim]By Zypher Systems[/dim]", border_style="blue"))
        snapshots = list_snapshots(config)
        if snapshots:
            display_snapshots(snapshots)
        else:
            console.print("[yellow]No snapshots to display[/yellow]")
        
        console.print("\n[bold]Menu:[/bold]")
        console.print("1. Create Snapshot")
        console.print("2. Delete Snapshot")
        console.print("3. Compare Snapshots")
        console.print("4. Rollback Snapshot")
        console.print("5. Snapshot Details")
        console.print("6. Cleanup Management")
        console.print("7. Exit")
        
        choice = Prompt.ask("Select an option", choices=["1", "2", "3", "4", "5", "6", "7"], default="7")
        
        if choice == "1":
            desc = Prompt.ask("Enter snapshot description", default="Manual snapshot")
            create_snapshot(config, desc)
            console.print("Press Enter to continue...")
            console.input()
        
        elif choice == "2":
            number = select_snapshot(snapshots, "Select snapshot to delete")
            if number and Confirm.ask(f"Delete snapshot {number}?", default=False):
                delete_snapshot(config, number)
            console.print("Press Enter to continue...")
            console.input()
        
        elif choice == "3":
            console.print("Select two snapshots to compare")
            num1 = select_snapshot(snapshots, "Select first snapshot")
            if num1:
                num2 = select_snapshot(snapshots, "Select second snapshot")
                if num2:
                    compare_snapshots(config, num1, num2)
        
        elif choice == "4":
            number = select_snapshot(snapshots, "Select snapshot for rollback")
            if number:
                rollback_guidance(config, number)
            console.print("Press Enter to continue...")
            console.input()
        
        elif choice == "5":
            number = select_snapshot(snapshots, "Select snapshot for details")
            if number:
                snapshot_details(config, number)
            console.print("Press Enter to continue...")
            console.input()
        
        elif choice == "6":
            console.print("\n[bold]Cleanup Options:[/bold]")
            console.print("1. Run Cleanup")
            console.print("2. View Cleanup Settings")
            console.print("3. Edit Cleanup Settings")
            cleanup_choice = Prompt.ask("Select cleanup option", choices=["1", "2", "3"], default="1")
            if cleanup_choice == "1":
                cleanup_type = Prompt.ask("Enter cleanup type (timeline, number, empty-pre-post)", default="timeline")
                cleanup_snapshots(config, cleanup_type)
            elif cleanup_choice == "2":
                view_cleanup_settings(config)
            elif cleanup_choice == "3":
                edit_cleanup_settings(config)
            console.print("Press Enter to continue...")
            console.input()
        
        elif choice == "7":
            console.print("[yellow]Exiting...[/yellow]")
            break

if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        console.print("\n[yellow]Exiting...[/yellow]")