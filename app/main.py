import typer
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.progress import Progress, TaskID
from rich import print as rprint
import os
import shutil
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional
from .services.database import DatabaseService
from .services.ai_service import AIService
from .models.models import Show, Episode
from .utils.xml_parser import parse_rss_feed
from .utils.episode_helper import parse_episode_range, get_episode_description

app = typer.Typer()
console = Console()
db = DatabaseService("app/data/urls.db")
ai = AIService()

# Create a sub-application for list commands
list_app = typer.Typer()
app.add_typer(list_app, name="list", help="List shows and episodes")

# Display help when no command is provided for list_app
@list_app.callback(invoke_without_command=True)
def list_main(ctx: typer.Context):
    """List shows or episodes"""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()

# Create a sub-application for delete commands
delete_app = typer.Typer()
app.add_typer(delete_app, name="delete", help="Delete shows or episodes")

# Display help when no command is provided for delete_app
@delete_app.callback(invoke_without_command=True)
def delete_main(ctx: typer.Context):
    """Delete shows or episodes"""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()

# Display help when no command is provided
@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Podcast archive management tool"""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()

def prompt_for_show_id() -> int:
    """Display all shows and prompt the user to select one by ID"""
    shows = db.list_shows()
    
    if not shows:
        console.print("[yellow]No shows found in the database. Add a show first.[/yellow]")
        raise typer.Exit(code=1)
        
    show_table = Table(show_header=True, header_style="bold magenta")
    show_table.add_column("ID", style="dim")
    show_table.add_column("Name")
    show_table.add_column("URL")
    show_table.add_column("Episodes", style="dim")
    
    # Create a dictionary of valid show IDs for quick lookup
    valid_show_ids = {show.id for show in shows}
    
    for show in shows:
        episodes = db.list_episodes(show.id)
        show_table.add_row(
            str(show.id),
            show.name,
            show.url,
            str(len(episodes))
        )
    
    console.print("[bold]Available Shows:[/bold]")
    console.print(show_table)
    
    # Loop until a valid show ID is provided
    while True:
        # Prompt user for show ID
        show_id = IntPrompt.ask("Enter the ID of the show")
        
        # Validate the ID
        if show_id in valid_show_ids:
            return show_id
        else:
            console.print(f"[red]Show with ID {show_id} not found. Please try again.[/red]")

@delete_app.command("show")
def delete_show(
    show_id: Optional[int] = typer.Argument(None, help="ID of the show to delete"),
    files_only: bool = typer.Option(False, "--files-only", "-f", help="Delete ONLY downloaded files, keep DB entry"),
    db_only: bool = typer.Option(False, "--db-only", "-d", help="Delete ONLY DB entry, keep downloaded files"),
    downloads: bool = typer.Option(False, "--downloads", "--dl", help="Delete ONLY downloads (same as --files-only)"),
    all_no_prompt: bool = typer.Option(False, "--all", "-a", help="Delete BOTH DB entry AND downloads without prompting"),
    force: bool = typer.Option(False, "--force", help="Force deletion even if no downloaded episodes are found in database")
):
    """Delete a show and/or its downloaded files
    
    Examples:
      parchive delete show 3              # Interactive deletion with prompts for both DB and downloads
      parchive delete show 3 --downloads  # Delete just the downloaded files 
      parchive delete show 3 --db-only    # Delete just the database entry
      parchive delete show 3 --all        # Delete both DB entry and downloads without prompting
      parchive delete show 3 --force      # Force deletion even if no downloaded episodes are found in database
    """
    # If no show ID is provided, first display available shows and prompt for selection
    if show_id is None:
        try:
            show_id = prompt_for_show_id()
        except typer.Exit:
            # This is raised when there are no shows in the database
            # The error message is already displayed in prompt_for_show_id
            return
    
    # Get show from database
    show = db.get_show(show_id)
    if not show:
        console.print(f"[red]Show {show_id} not found[/red]")
        return
    
    # Get all episodes for the show
    episodes = db.list_episodes(show_id)
    
    if not episodes:
        console.print(f"[yellow]No episodes found for show: {show.name}[/yellow]")
        return
    
    # Show the entry to be deleted
    console.print(f"\n[bold]Entry to delete:[/bold]")
    console.print(f"Show: [cyan]{show.name}[/cyan]")
    console.print(f"Episodes: [cyan]{len(episodes)}[/cyan]")
    console.print(f"URL: [cyan]{show.url}[/cyan]\n")
    
    # Handle mutually exclusive options
    if files_only and db_only:
        console.print("[red]Error: Cannot specify both --files-only and --db-only[/red]")
        return
    
    # Determine download directory
    download_dir = Path(f"downloads/{show_id}")
    has_downloads = download_dir.exists()
    
    # Report on downloads if they exist
    if has_downloads:
        file_count = sum(1 for _ in download_dir.glob('*'))
        console.print(f"[yellow]Found {file_count} files in {download_dir}[/yellow]")
    else:
        console.print(f"[yellow]No download directory found for show: {show.name} (ID: {show_id})[/yellow]")
        if files_only:
            console.print("[yellow]Nothing to delete[/yellow]")
            return
    
    # Default behavior: delete both DB entry and files
    delete_db = not files_only
    delete_files = not db_only and has_downloads
    
    # Skip prompts if using the --all flag
    if not all_no_prompt:
        # Ask about database entry first
        if delete_db:
            delete_db = Confirm.ask(f"Delete database entry for '{show.name}'?")
            if not delete_db and not delete_files:
                console.print("[yellow]Operation cancelled[/yellow]")
                return
        
        # Only ask about files if directory exists
        if delete_files:
            delete_files = Confirm.ask(f"Delete downloaded files for '{show.name}'?")
            if not delete_files and not delete_db:
                console.print("[yellow]No deletions requested, operation cancelled[/yellow]")
                return
    else:
        # If using --all flag, print what we're doing
        operations = []
        if delete_db:
            operations.append("database entry")
        if delete_files:
            operations.append("downloaded files")
            
        console.print(f"[yellow]Auto-deleting: {', '.join(operations)}[/yellow]")
    
    # Perform deletions
    if delete_files and has_downloads:
        try:
            # Count files before deletion
            file_count = sum(1 for _ in download_dir.glob('*'))
            
            # Delete the entire directory recursively
            import shutil
            shutil.rmtree(download_dir)
            
            console.print(f"[green]Deleted download directory with {file_count} files for '{show.name}'[/green]")
        except Exception as e:
            console.print(f"[red]Error deleting download directory: {str(e)}[/red]")
    
    if delete_db:
        # When deleting the whole show, we use delete_show which will also delete all episodes
        if db.delete_show(show_id):
            console.print(f"[green]Deleted show '{show.name}' and its {len(episodes)} episodes from database (ID: {show_id})[/green]")
        else:
            console.print(f"[red]Failed to delete show {show_id} from database[/red]")

@delete_app.command("episodes")
def delete_episodes(
    show_id: Optional[int] = typer.Argument(None, help="ID of the show"),
    all_episodes: bool = typer.Option(False, "--all", "-a", help="Delete all episodes without prompting")
):
    """Delete specific episodes of a show
    
    Examples:
      parchive delete episodes 3       # Interactive deletion with choices for range or single episodes
      parchive delete episodes 3 --all  # Delete all episodes without prompting
    """
    # If no show ID is provided, first display available shows and prompt for selection
    if show_id is None:
        try:
            show_id = prompt_for_show_id()
        except typer.Exit:
            # This is raised when there are no shows in the database
            # The error message is already displayed in prompt_for_show_id
            return
    
    # Get show from database
    show = db.get_show(show_id)
    if not show:
        console.print(f"[red]Show {show_id} not found[/red]")
        return
    
    # Get all episodes for the show
    episodes = db.list_episodes(show_id)
    
    if not episodes:
        console.print(f"[yellow]No episodes found for show: {show.name}[/yellow]")
        return
    
    # Check if any episodes are downloaded
    downloaded_episodes = [ep for ep in episodes if ep.is_downloaded]
    if not downloaded_episodes:
        console.print(f"[yellow]No downloaded episodes found for show: {show.name}[/yellow]")
        return
    
    # Display available episodes
    episode_table = Table(show_header=True, header_style="bold magenta")
    episode_table.add_column("Number", style="dim")
    episode_table.add_column("Title")
    episode_table.add_column("Status", style="dim")
    
    # Show only downloaded episodes
    for episode in downloaded_episodes:
        episode_table.add_row(
            episode.episode_number,
            episode.title,
            "[green]Downloaded[/green]"
        )
    
    console.print(f"[bold]Downloaded episodes for {show.name}:[/bold]")
    console.print(episode_table)
    
    # If all_episodes flag is set, delete all downloaded episodes
    if all_episodes:
        delete_option = "all"
        console.print("[yellow]Auto-deleting all episodes[/yellow]")
    else:
        # Ask user what they want to delete
        console.print(f"[bold]Delete options for '{show.name}':[/bold]")
        valid_options = ["none", "all", "single", "range"]
        console.print("Options: " + ", ".join(valid_options) + " (default: none)")
        console.print("[yellow]Tips:[/yellow]")
        console.print("  - [cyan]single[/cyan]: Delete one episode by number")
        console.print("  - [cyan]range[/cyan]: Delete a range like 1-5")
        console.print("  - [cyan]all[/cyan]: Delete all downloaded episodes")
        
        delete_option = Prompt.ask(
            "Choose an option",
            default="none",
            choices=valid_options,
            show_choices=False
        )
    
    if delete_option == "none":
        console.print("[yellow]Operation cancelled[/yellow]")
        return
        
    if delete_option == "all":
        # Confirm deletion of all episodes
        if not all_episodes:  # Skip confirmation if --all flag was used
            confirm = Confirm.ask(f"Are you sure you want to delete ALL episodes for '{show.name}'?")
            if not confirm:
                console.print("[yellow]Operation cancelled[/yellow]")
                return
        
        # Delete all downloaded episodes
        download_dir = Path(f"downloads/{show_id}")
        
        if download_dir.exists():
            # Count files before deletion
            file_count = sum(1 for _ in download_dir.glob('*.*') if not _.name.startswith('metadata') and _.name != 'feed.xml' and _.name != 'cover.jpg')
            
            # Delete all episode files but preserve metadata and feed files
            deleted_count = 0
            for file_path in download_dir.glob('*.*'):
                # Skip metadata.json, feed.xml and cover.jpg
                if file_path.name == 'metadata.json' or file_path.name == 'feed.xml' or file_path.name == 'cover.jpg':
                    continue
                    
                try:
                    file_path.unlink()
                    deleted_count += 1
                    console.print(f"[green]Deleted file: {file_path.name}[/green]")
                except Exception as e:
                    console.print(f"[red]Error deleting file {file_path}: {str(e)}[/red]")
                    
            console.print(f"[green]Deleted {deleted_count} of {file_count} episode files for '{show.name}'[/green]")
        else:
            console.print(f"[yellow]No download directory found for show: {show.name}[/yellow]")
            
        # Mark all episodes as not downloaded in the database
        updated_count = 0
        for episode in episodes:
            if db.update_episode_download_status(episode.id, False):
                updated_count += 1
                
        console.print(f"[green]Marked {updated_count} episodes as not downloaded in the database[/green]")
        return
    
    elif delete_option == "range":
        # Prompt for range with examples
        console.print("[yellow]Examples:[/yellow]")
        console.print("  - Single range: [cyan]1-5[/cyan]")
        console.print("  - Multiple ranges: [cyan]1-5,10-15,20[/cyan]")
        console.print("  - Individual episodes: [cyan]3,7,9[/cyan]")
        
        range_input = Prompt.ask("Enter episode range")
        
        # Parse the range using our episode_helper function
        from .utils.episode_helper import parse_episode_range
        episode_indices = parse_episode_range(range_input)
        
        if not episode_indices:
            console.print("[red]Invalid range format or empty range[/red]")
            return
            
        # Find episodes within the specified indices
        range_episodes = []
        for episode in episodes:
            try:
                episode_num = int(episode.episode_number)
                if episode_num in episode_indices and episode.is_downloaded:
                    range_episodes.append(episode)
            except ValueError:
                # Skip episodes with non-numeric episode numbers
                pass
        
        if not range_episodes:
            console.print(f"[yellow]No downloaded episodes found in the specified range[/yellow]")
            return
            
        # Confirm deletion of range
        from .utils.episode_helper import get_episode_description
        episode_desc = get_episode_description(episode_indices)
        console.print(f"[bold]Found {len(range_episodes)} downloaded episodes for {episode_desc}[/bold]")
        confirm = Confirm.ask(f"Are you sure you want to delete these episodes?")
        if not confirm:
            console.print("[yellow]Operation cancelled[/yellow]")
            return
            
        # Delete each episode in the range individually
        download_dir = Path(f"downloads/{show_id}")
        deleted_files = 0
        
        for episode in range_episodes:
            # Delete the episode file from disk
            if episode.file_hash and download_dir.exists():
                # Look for files with this hash
                for file_path in download_dir.glob(f"*_{episode.file_hash}*"):
                    try:
                        file_path.unlink()
                        deleted_files += 1
                        console.print(f"[green]Deleted file: {file_path.name}[/green]")
                    except Exception as e:
                        console.print(f"[red]Error deleting file {file_path}: {str(e)}[/red]")
            
            # Delete from database
            db.delete_episode(episode.id)
            
        console.print(f"[green]Completed deletion of {len(range_episodes)} episodes and {deleted_files} files for {episode_desc} of '{show.name}'[/green]")
        return
    
    elif delete_option == "single":
        # Filter to only show downloaded episodes
        downloaded_episodes = [ep for ep in episodes if ep.is_downloaded]
        
        if not downloaded_episodes:
            console.print(f"[yellow]No downloaded episodes found for show: {show.name}[/yellow]")
            return
            
        # Create a mapping from episode number to the actual episode
        episode_number_map = {}
        
        for episode in downloaded_episodes:
            try:
                # Try to convert episode number to integer for sorting
                ep_num = int(episode.episode_number)
                episode_number_map[ep_num] = episode
                
            except ValueError:
                # If episode number is not a number, use it as is
                episode_number_map[episode.episode_number] = episode
            
        # Loop until a valid episode number is provided
        while True:
            # Prompt for episode number to delete
            episode_input = Prompt.ask("Enter the number of the episode to delete")
            
            # Try to handle both numeric and non-numeric episode numbers
            try:
                # Try to interpret as integer
                episode_num = int(episode_input)
                if episode_num in episode_number_map:
                    episode = episode_number_map[episode_num]
                    break
                else:
                    console.print(f"[red]Episode number {episode_input} not found. Please enter a valid number from the list.[/red]")
            except ValueError:
                # If not an integer, check as string
                if episode_input in episode_number_map:
                    episode = episode_number_map[episode_input]
                    break
                else:
                    console.print(f"[red]Episode number {episode_input} not found. Please enter a valid number from the list.[/red]")
        
        # Delete the episode file from disk
        download_dir = Path(f"downloads/{show_id}")
        if episode.file_hash and download_dir.exists():
            # Look for files with this hash
            for file_path in download_dir.glob(f"*_{episode.file_hash}*"):
                try:
                    file_path.unlink()
                    console.print(f"[green]Deleted file: {file_path.name}[/green]")
                except Exception as e:
                    console.print(f"[red]Error deleting file {file_path}: {str(e)}[/red]")
        
        # Delete from database
        if db.delete_episode(episode.id):
            console.print(f"[green]Deleted episode '{episode.title}' (Number: {episode.episode_number})[/green]")
        else:
            console.print(f"[red]Failed to delete episode {episode.episode_number}[/red]")
        
        return

@app.command()
def analyze(
    show_id: Optional[int] = typer.Argument(None, help="ID of the show to analyze"),
    episode_number: Optional[str] = typer.Option(None, "--episode", "-e", help="Episode number to analyze")
):
    """Analyze a show or episode using AI"""
    try:
        # Check if AI service is available
        if not ai.is_model_available:
            console.print("[red]Warning: AI analysis service is not available[/red]")
            console.print("[yellow]The local AI model server appears to be offline.[/yellow]")
            console.print("[yellow]Make sure the model server is running at http://localhost:12434/engines/v1[/yellow]")
            
            # Ask if the user wants to continue with limited functionality
            if not typer.confirm("Continue without AI analysis?", default=True):
                return

        # If no show_id provided, prompt user to select one
        if show_id is None:
            try:
                show_id = prompt_for_show_id()
            except typer.Exit:
                # If the user doesn't have any shows, show the help
                ctx = typer.Context(analyze)
                typer.echo(ctx.get_help())
                raise typer.Exit()
        
        # Get the show
        show = db.get_show(show_id)
        if not show:
            console.print(f"[red]Show with ID {show_id} not found[/red]")
            return
            
        # If episode_number is provided, find the matching episode from the show
        target_episode = None
        if episode_number is not None:
            episodes = db.list_episodes(show_id)
            for episode in episodes:
                if episode.episode_number == episode_number:
                    target_episode = episode
                    break
            
            if target_episode is None:
                console.print(f"[red]Episode number {episode_number} not found for show '{show.name}'[/red]")
                return
            
        # If we found a target episode, analyze it
        if target_episode:
            # Display episode information regardless of AI availability
            console.print(f"\n[bold]Episode Information:[/bold]")
            info_table = Table(show_header=True, header_style="bold cyan")
            info_table.add_column("Field")
            info_table.add_column("Value")
            
            info_table.add_row("Show", show.name)
            info_table.add_row("Episode Number", target_episode.episode_number)
            info_table.add_row("Title", target_episode.title)
            info_table.add_row("Published", target_episode.published_at.strftime("%Y-%m-%d") if target_episode.published_at else "Unknown")
            info_table.add_row("URL", target_episode.url)
            info_table.add_row("Downloaded", "Yes" if target_episode.is_downloaded else "No")
            
            console.print(info_table)
                
            # Only attempt to analyze if AI is available
            if ai.is_model_available:
                console.print(f"\n[yellow]Analyzing episode: {target_episode.title} (Show: {show.name})...[/yellow]")
                analysis = ai.analyze_episode(target_episode, show.name)
                console.print("\n[green]Analysis:[/green]")
                console.print(analysis)
        else:
            # Display show information regardless of AI availability
            console.print(f"\n[bold]Show Information:[/bold]")
            info_table = Table(show_header=True, header_style="bold cyan")
            info_table.add_column("Field")
            info_table.add_column("Value")
            
            info_table.add_row("Name", show.name)
            info_table.add_row("Feed URL", show.url)
            
            # Get episode count
            episodes = db.list_episodes(show_id)
            info_table.add_row("Total Episodes", str(len(episodes)))
            
            downloaded_count = sum(1 for ep in episodes if ep.is_downloaded)
            info_table.add_row("Downloaded Episodes", str(downloaded_count))
            
            console.print(info_table)
            
            # Only attempt to analyze if AI is available
            if ai.is_model_available:
                console.print(f"\n[yellow]Analyzing show: {show.name}...[/yellow]")
                analysis = ai.analyze_show(show)
                console.print("\n[green]Analysis:[/green]")
                console.print(analysis)
            
            # If this is a show analysis, offer to list episodes that can be analyzed
            if episodes:
                console.print(f"\n[yellow]This show has {len(episodes)} episodes that can be analyzed.[/yellow]")
                console.print("[cyan]To analyze a specific episode, use:[/cyan]")
                console.print(f" parchive analyze {show_id} --episode <episode_number>")
                
                # Show a few episode examples
                sample_size = min(3, len(episodes))
                console.print("\n[yellow]Sample episodes:[/yellow]")
                episode_table = Table(show_header=True, header_style="bold magenta")
                episode_table.add_column("Episode #")
                episode_table.add_column("Title")
                
                for episode in episodes[:sample_size]:
                    episode_table.add_row(
                        episode.episode_number,
                        episode.title
                    )
                
                console.print(episode_table)
                console.print(f"[cyan]To see all episodes, use: parchive list episodes {show_id}[/cyan]")
    except typer.BadParameter:
        ctx = typer.Context(analyze)
        typer.echo(ctx.get_help())
        raise typer.Exit()

def download_image(image_url: str, output_path: Path, progress=None) -> bool:
    """
    Download an image from a URL and save it to the specified path.
    
    Args:
        image_url: URL of the image to download
        output_path: Path where the image will be saved
        progress: Optional progress object for console output
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not image_url:
        if progress:
            progress.console.print(f"[yellow]No image URL provided for {output_path.stem}[/yellow]")
        return False
        
    try:
        import requests
        # Use a short timeout for images
        with requests.get(image_url, stream=True, timeout=30) as response:
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        
            if progress:
                progress.console.print(f"[green]Downloaded image: {output_path.name}[/green]")
            return True
    except Exception as e:
        if progress:
            progress.console.print(f"[red]Error downloading image: {str(e)}[/red]")
        return False

def download_episodes(show_id: int, episode_input: str = "all", skip_reindex: bool = False):
    """
    Download episodes from a feed URL.
    
    Args:
        show_id: ID of the show in the database
        episode_input: Episode range to download (default: "all")
        skip_reindex: Skip the reindex check for internal use
    """
    # Get show from database
    show = db.get_show(show_id)
    if not show:
        console.print(f"[red]Show {show_id} not found[/red]")
        return
    
    # Variables that might be needed regardless of reindex
    db_episodes = db.list_episodes(show_id)
    db_urls = {episode.url: episode for episode in db_episodes}
    feed_episodes = []
    feed_urls = {}
    
    # Run reindex check first to ensure we have the latest metadata
    if not skip_reindex:
        console.print("[yellow]Checking for updates to feed data...[/yellow]")
        
        # Parse RSS feed
        feed_data = parse_rss_feed(show.url)
        if not feed_data or 'episodes' not in feed_data or not feed_data['episodes']:
            console.print("[red]No episodes found in feed[/red]")
            return
            
        # Process feed episodes for comparison
        for i, episode_data in enumerate(feed_data['episodes'], 1):
            title = episode_data.get('title', f"Episode {i}")
            url = episode_data.get('url', '')
            published = episode_data.get('published_at')
            
            # Try to extract episode number from title
            episode_number = str(i)
            import re
            match = re.match(r'^(\d+)[\s:\-\.]+', title)
            if match:
                episode_number = match.group(1)
            
            feed_episodes.append({
                'title': title,
                'url': url,
                'episode_number': episode_number,
                'published_at': published
            })
        
        # Compare episodes by URL (primary key for matching)
        feed_urls = {episode['url']: episode for episode in feed_episodes}
        
        # Find differences
        new_episodes = [ep for url, ep in feed_urls.items() if url not in db_urls]
        missing_episodes = [ep for url, ep in db_urls.items() if url not in feed_urls]
            
        # Check for modified episodes (same URL but different title or episode number)
        modified_episodes = []
        for url, feed_ep in feed_urls.items():
            if url in db_urls:
                db_ep = db_urls[url]
                if feed_ep['title'] != db_ep.title or feed_ep['episode_number'] != db_ep.episode_number:
                    modified_episodes.append({
                        'feed': feed_ep,
                        'db': db_ep
                    })
        
        # Display differences
        has_differences = new_episodes or missing_episodes or modified_episodes
        
        if has_differences:
            console.print("[bold yellow]Feed data has changed since last update.[/bold yellow]")
            
            # Display summaries of changes
            if new_episodes:
                console.print(f"[cyan]New episodes: {len(new_episodes)}[/cyan]")
            if missing_episodes:
                console.print(f"[cyan]Episodes removed from feed: {len(missing_episodes)}[/cyan]")
            if modified_episodes:
                console.print(f"[cyan]Episodes with updated metadata: {len(modified_episodes)}[/cyan]")
                
            # Prompt for reindex
            proceed = Confirm.ask("\nUpdate database with latest feed data before downloading?", default=True)
            if proceed:
                # Update the database with latest feed data
                with Progress() as progress:
                    task = progress.add_task("[cyan]Updating episodes metadata...", total=len(feed_episodes))
                    
                    for episode_data in feed_episodes:
                        title = episode_data['title']
                        url = episode_data['url']
                        episode_number = episode_data['episode_number']
                        published_at = episode_data['published_at']
                        
                        # Check if episode already exists in database
                        existing_episode = None
                        for db_ep in db_episodes:
                            if db_ep.url == url:
                                existing_episode = db_ep
                                break
                        
                        if existing_episode:
                            # Update existing episode
                            existing_episode.title = title
                            existing_episode.episode_number = episode_number
                            existing_episode.published_at = published_at
                            db.update_episode(existing_episode)
                        else:
                            # Create new episode
                            new_ep = Episode(
                                show_id=show_id,
                                title=title,
                                url=url,
                                episode_number=episode_number,
                                published_at=published_at
                            )
                            db.add_episode(new_ep)
                        
                        progress.update(task, advance=1)
                
                console.print(f"[green]Successfully updated metadata for {len(feed_episodes)} episodes[/green]")
            else:
                console.print("[yellow]Continuing with download using existing metadata[/yellow]")
        else:
            console.print("[green]Feed data is up-to-date[/green]")
    
    # Parse RSS feed (either freshly pulled or reused from reindex)
    if not 'feed_data' in locals() or feed_data is None:
        console.print(f"[yellow]Fetching feed: {show.name}[/yellow]")
        feed_data = parse_rss_feed(show.url)
        
        if not feed_data or 'episodes' not in feed_data or not feed_data['episodes']:
            console.print("[red]No episodes found in feed[/red]")
            return
    
    # Parse episode range
    episode_range = parse_episode_range(episode_input)
    episodes_to_download = feed_data['episodes']
    
    # Filter episodes if a specific range was requested
    if episode_range:
        console.print(f"[yellow]Filtering to {len(episode_range)} specific episode(s)[/yellow]")
        filtered_episodes = []
        
        # If specific episodes requested (not all), limit to those episodes
        for i, episode in enumerate(episodes_to_download):
            # We're 0-indexed internally, but user-facing is 1-indexed
            user_facing_index = i + 1
            if user_facing_index in episode_range:
                filtered_episodes.append(episode)
                
        episodes_to_download = filtered_episodes
        console.print(f"[green]Found {len(filtered_episodes)} matching episodes[/green]")
    
    if not episodes_to_download:
        console.print("[red]No episodes match the specified range[/red]")
        return
    
    # Create download directory using show ID
    download_dir = Path(f"downloads/{show_id}")
    download_dir.mkdir(parents=True, exist_ok=True)
    
    # Create/update metadata.json with show information
    import json
    from datetime import datetime
    
    now = datetime.now().isoformat()
    metadata = {
        "show_id": show_id,
        "name": show.name,
        "url": show.url,
        "last_download": now,
        "last_rss_update": now,
        "episode_filter": episode_input
    }
    
    with open(download_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    
    # Always download a fresh copy of the RSS feed
    rss_path = download_dir / "feed.xml"
    console.print("[yellow]Downloading RSS feed for offline archive...[/yellow]")
    if download_rss_feed(show.url, rss_path):
        console.print(f"[green]Saved RSS feed to {rss_path}[/green]")
    else:
        console.print("[red]Failed to download RSS feed[/red]")
        
    # Download show cover image if available
    if hasattr(show, 'image_url') and show.image_url:
        cover_path = download_dir / "cover.jpg"
        console.print("[yellow]Downloading show cover image...[/yellow]")
        if download_image(show.image_url, cover_path):
            console.print(f"[green]Saved show cover image to {cover_path}[/green]")
        else:
            console.print("[red]Failed to download show cover image[/red]")
            
    # Try to get show image from feed data if not already available
    elif feed_data and 'image_url' in feed_data:
        cover_path = download_dir / "cover.jpg"
        console.print("[yellow]Downloading show cover image from feed...[/yellow]")
        if download_image(feed_data['image_url'], cover_path):
            console.print(f"[green]Saved show cover image to {cover_path}[/green]")
            
            # Update the show object with the image URL
            if hasattr(show, 'image_url'):
                show.image_url = feed_data['image_url']
                db.update_show(show)
    
    # Get episode description
    if episode_range:
        episode_desc = get_episode_description(episode_range)
    else:
        episode_desc = "all episodes"
    
    # Download episodes with progress bar
    console.print(f"[green]Downloading {len(episodes_to_download)} episodes ({episode_desc}) to {download_dir} (Show ID: {show_id})...[/green]")
    
    with Progress() as progress:
        overall_task = progress.add_task(f"[yellow]Downloading episodes for {show.name}...", total=len(episodes_to_download))
        
        for i, episode in enumerate(episodes_to_download, 1):
            # Use a default title with the index if no title is available
            episode_title = episode.get('title', f"Episode {i}")
            episode_url = episode.get('url')
            
            # Get the actual episode number from feed or use the index
            episode_number = episode.get('episode_number')
            if not episode_number:
                # Try to extract episode number from title like "123: Title"
                import re
                match = re.match(r'^(\d+)[\s:\-\.]+', episode_title)
                if match:
                    episode_number = match.group(1)
                else:
                    # Fall back to our index
                    episode_number = str(i)
                    
            # Ensure episode_number is at least 3 digits with leading zeros
            episode_number = episode_number.zfill(3)
            
            if not episode_url:
                progress.console.print(f"[red]No download URL for episode: {episode_title}[/red]")
                progress.update(overall_task, advance=1)
                continue
            
            # Extract just the MP3 filename from the URL and remove query parameters
            url_filename = os.path.basename(episode_url.split('?')[0])
            
            # Get file extension from URL or default to .mp3
            file_extension = os.path.splitext(url_filename)[1]
            if not file_extension:
                file_extension = ".mp3"
            
            # Generate a hash of the episode URL to use as the filename
            import hashlib
            # Create a unique hash incorporating show ID, episode number and URL
            hash_input = f"{show_id}_{episode_number}_{episode_url}"
            file_hash = hashlib.md5(hash_input.encode()).hexdigest()
            
            # Convert episode number to an integer if possible, otherwise use as-is
            episode_num = episode_number
            try:
                # Remove leading zeros for display
                episode_num = str(int(episode_number))
            except (ValueError, TypeError):
                pass
                
            # Use the episode number and hash as the filename
            output_path = download_dir / f"{episode_num}_{file_hash}{file_extension}"
            
            # Define the path for the episode image (using same base filename with .jpg extension)
            image_path = download_dir / f"{episode_num}_{file_hash}.jpg"
            
            # Find or create the corresponding episode entry in the database
            # First, find the matching episode from our already parsed feed
            matched_episode = None
            for db_episode in db.list_episodes(show_id):
                if db_episode.url == episode_url:
                    matched_episode = db_episode
                    break
                    
            # If we found a matching episode, update its download status
            if matched_episode:
                # Update the database with the download status and file hash
                db.update_episode_download_status(matched_episode.id, True, file_hash)
            
            # Skip if file already exists
            if output_path.exists():
                progress.console.print(f"[blue]File already exists: {output_path.name}[/blue]")
                
                # If the audio exists but the image doesn't, try to download the image
                if not image_path.exists() and 'image_url' in episode:
                    progress.console.print(f"[yellow]Downloading missing image for: {episode_title}[/yellow]")
                    download_image(episode.get('image_url'), image_path, progress)
                    
                progress.update(overall_task, advance=1)
                continue
                
            # Download the file with retries
            max_retries = 3
            retry_count = 0
            success = False
            
            while retry_count < max_retries and not success:
                try:
                    if retry_count > 0:
                        progress.console.print(f"[yellow]Retry {retry_count}/{max_retries} for {episode_title}...[/yellow]")
                    
                    download_task = progress.add_task(f"[cyan]Downloading: {episode_title}", total=1)
                    
                    # Use requests instead of urllib for better handling of large files
                    import requests
                    with requests.get(episode_url, stream=True, timeout=60) as response:
                        response.raise_for_status()
                        total_size = int(response.headers.get('content-length', 0))
                        block_size = 8192  # 8 KB
                        downloaded = 0
                        
                        with open(output_path, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=block_size):
                                if chunk:
                                    f.write(chunk)
                                    downloaded += len(chunk)
                                    if total_size > 0:
                                        progress.update(download_task, 
                                            completed=min(downloaded / total_size, 1.0))
                    
                    progress.console.print(f"[green]Downloaded: {output_path.name}[/green]")
                    success = True
                    
                    # Download episode image if available
                    if 'image_url' in episode and episode.get('image_url'):
                        if download_image(episode.get('image_url'), image_path, progress):
                            # Update the image file hash in the database if episode was found
                            if matched_episode:
                                db.update_episode_image_file_hash(matched_episode.id, file_hash)
                    
                    progress.update(overall_task, advance=1)
                except (requests.RequestException, Exception) as e:
                    progress.console.print(f"[red]Error downloading {episode_title}: {str(e)}[/red]")
                    retry_count += 1
                    if retry_count >= max_retries:
                        progress.console.print(f"[red]Failed after {max_retries} attempts for {episode_title}[/red]")
            
            progress.update(overall_task, advance=1)
    
    console.print(f"[green]Download complete! Files saved to {download_dir} with metadata.json[/green]")

@app.command()
def download(
    show_id: Optional[int] = typer.Argument(None, help="ID of the show in the database"),
    episodes: str = typer.Option(None, "--episodes", "-e", help="Episodes to download (all, single, range, or specific number)"),
    skip_reindex: bool = typer.Option(False, "--skip-reindex", help="Skip checking for feed updates before downloading")
):
    """Download episodes from a feed URL."""
    # If no show_id provided, prompt user to select one
    if show_id is None:
        try:
            show_id = prompt_for_show_id()
        except typer.Exit:
            # If the user doesn't have any shows, just show a message and exit
            console.print("[yellow]No shows available. Add a show first using 'parchive add-show'[/yellow]")
            raise typer.Exit()
    
    # Get the show to display its name
    show = db.get_show(show_id)
    if not show:
        console.print(f"[red]Show {show_id} not found[/red]")
        return
    
    # If episodes not specified via command line, prompt the user
    if episodes is None:
        # Define valid options and provide validation
        valid_episode_options = ["all", "single", "range"]
        
        # Ask for episode selection
        console.print(f"[bold]Download options for '{show.name}':[/bold]")
        console.print("[yellow]Options:[/yellow]")
        console.print("  - [cyan]all[/cyan]: Download all episodes")
        console.print("  - [cyan]single[/cyan]: Download one episode by number")
        console.print("  - [cyan]range[/cyan]: Download a range like 1-5")
        
        episode_input = Prompt.ask(
            "Choose an option",
            default="all",
            choices=valid_episode_options,
            show_choices=False
        )
        
        episodes = episode_input
    
    # Handle special case for "single" input
    if episodes and episodes.lower() == "single":
        # Get all episodes for the show
        show_episodes = db.list_episodes(show_id)
        
        # Display episode list for selection
        episode_table = Table(show_header=True, header_style="bold magenta")
        episode_table.add_column("Number", style="dim")
        episode_table.add_column("Title")
        episode_table.add_column("Published", style="dim")
        episode_table.add_column("Status", style="dim")
        
        for episode in show_episodes:
            published = episode.published_at.strftime("%Y-%m-%d") if episode.published_at else "Unknown"
            
            # Determine download status
            if episode.is_downloaded:
                status = "[green]Downloaded[/green]"
            else:
                status = "[dim]Not downloaded[/dim]"
                
            episode_table.add_row(
                episode.episode_number,
                episode.title,
                published,
                status
            )
        
        console.print(f"[bold]Episodes for {show.name}:[/bold]")
        console.print(episode_table)
        
        # Prompt for a specific episode number
        episode_number = Prompt.ask("Enter the specific episode number to download")
        episodes = episode_number
        console.print(f"[green]Selected episode {episode_number}[/green]")
    
    # Handle special case for "range" input
    elif episodes and episodes.lower() == "range":
        # Get all episodes for the show
        show_episodes = db.list_episodes(show_id)
        
        # Find the highest episode number
        highest_episode = "1"
        for episode in show_episodes:
            try:
                # Check if episode number is a digit and update highest if needed
                if episode.episode_number.isdigit() and int(episode.episode_number) > int(highest_episode):
                    highest_episode = episode.episode_number
            except (ValueError, AttributeError):
                # Skip episodes with non-numeric episode numbers
                pass
            
        console.print(f"[bold]Specifying episode range for: {show.name}[/bold]")
        
        # Show examples for range input
        console.print("[yellow]Examples:[/yellow]")
        console.print("  - Single range: [cyan]1-5[/cyan]")
        console.print("  - Multiple ranges: [cyan]1-5,10-15,20[/cyan]")
        console.print("  - Individual episodes: [cyan]3,7,9[/cyan]")
        
        # Get the range input directly
        episodes = Prompt.ask("Enter episode range", default=f"1-{highest_episode}")
        
        # Check if the range is valid
        from .utils.episode_helper import parse_episode_range
        episode_indices = parse_episode_range(episodes)
        
        if not episode_indices and episodes.lower() != "all":
            console.print("[red]Invalid range format. Using default (all episodes)[/red]")
            episodes = "all"
        else:
            from .utils.episode_helper import get_episode_description
            episode_desc = get_episode_description(episode_indices)
            console.print(f"[green]Selected {episode_desc}[/green]")
    
    # Default to "all" if episodes is still None
    if episodes is None:
        episodes = "all"
    
    # Continue with normal download process
    download_episodes(show_id, episodes, skip_reindex)

@list_app.command("shows")
def list_shows():
    """List all shows"""
    shows = db.list_shows()
    
    if not shows:
        console.print("[yellow]No shows found[/yellow]")
        return
        
    show_table = Table(show_header=True, header_style="bold magenta")
    show_table.add_column("ID", style="dim")
    show_table.add_column("Name")
    show_table.add_column("URL")
    show_table.add_column("Episodes", style="dim")
    
    for show in shows:
        episodes = db.list_episodes(show.id)
        show_table.add_row(
            str(show.id),
            show.name,
            show.url,
            str(len(episodes))
        )
    
    console.print(show_table)

@list_app.command("episodes")
def list_episodes(
    show_id: Optional[int] = typer.Argument(None, help="ID of the show"),
    sort: str = typer.Option("published", "--sort", "-s", help="Sort order: id, number, published (default)"),
    status: str = typer.Option("all", "--status", "-st", help="Filter by status: all, downloaded, not-downloaded, deleted"),
    downloaded_only: bool = typer.Option(False, "--downloaded", "-d", help="Show only downloaded episodes")
):
    """List all episodes for a show"""
    # If no show_id provided, prompt user to select one
    if show_id is None:
        try:
            show_id = prompt_for_show_id()
        except typer.Exit:
            # If the user doesn't have any shows, just show a message and exit
            # No need to try to get help context
            console.print("[yellow]No shows available. Add a show first using 'parchive add-show'[/yellow]")
            raise typer.Exit()
    
    # Get the show
    show = db.get_show(show_id)
    if not show:
        console.print(f"[red]Show with ID {show_id} not found[/red]")
        return
    
    # Map sort option to database field
    order_by = "published_at"  # default
    if sort == "id":
        order_by = "id"
    elif sort == "number":
        order_by = "episode_number"
        
    # Get episodes with the specified sort order
    episodes = db.list_episodes(show_id, order_by)
    
    if not episodes:
        console.print(f"[yellow]No episodes found for show: {show.name}[/yellow]")
        return
    
    # Filter episodes by status if requested
    if status != "all":
        filtered_episodes = []
        for episode in episodes:
            if status == "downloaded" and episode.is_downloaded:
                filtered_episodes.append(episode)
            elif status == "not-downloaded" and not episode.was_downloaded:
                filtered_episodes.append(episode)
            elif status == "deleted" and episode.was_downloaded and not episode.is_downloaded:
                filtered_episodes.append(episode)
        
        episodes = filtered_episodes
        
        if not episodes:
            console.print(f"[yellow]No episodes with status '{status}' found for show: {show.name}[/yellow]")
            return
            
    # Apply downloaded_only filter if requested
    if downloaded_only:
        episodes = [ep for ep in episodes if ep.is_downloaded]
        
        if not episodes:
            console.print(f"[yellow]No downloaded episodes found for show: {show.name}[/yellow]")
            return
        
    # Display episodes
    status_display = f" [{status}]" if status != "all" else ""
    downloaded_display = " [downloaded only]" if downloaded_only else ""
    console.print(f"[bold]Episodes for {show.name}{status_display}{downloaded_display}:[/bold]")
    
    episode_table = Table(show_header=True, header_style="bold magenta")
    episode_table.add_column("Number")
    episode_table.add_column("Title")
    episode_table.add_column("Published", style="dim")
    episode_table.add_column("Status", style="dim")
    episode_table.add_column("Downloaded", style="dim")
    
    for episode in episodes:
        published = episode.published_at.strftime("%Y-%m-%d") if episode.published_at else "Unknown"
        
        # Determine download status
        if episode.is_downloaded:
            status = "[green]Downloaded[/green]"
            download_date = episode.download_date.strftime("%Y-%m-%d") if episode.download_date else "Unknown"
        elif episode.was_downloaded:
            status = "[yellow]Deleted[/yellow]"
            download_date = episode.deleted_date.strftime("%Y-%m-%d") if episode.deleted_date else "Unknown"
        else:
            status = "[dim]Not downloaded[/dim]"
            download_date = ""
            
        episode_table.add_row(
            episode.episode_number,
            episode.title,
            published,
            status,
            download_date
        )
    
    console.print(episode_table)

@app.command()
def add_show():
    """Add a new show (podcast)"""
    # Import at the top level to make sure it's available
    from .utils.episode_helper import parse_episode_range, get_episode_description
    
    url = Prompt.ask("Enter feed URL")
    name = ""
    feed_data = None
    
    # Try to parse XML if it looks like an RSS feed
    if url.startswith("http") and (".xml" in url or "feed" in url or "rss" in url):
        console.print("[yellow]Attempting to parse RSS feed...[/yellow]")
        feed_data = parse_rss_feed(url)
        
        if feed_data and 'title' in feed_data:
            feed_title = feed_data['title']
            use_title = Confirm.ask(f"Found title: [bold]{feed_title}[/bold]. Use this?", default=True)
            if use_title:
                name = feed_title
    
    # If we couldn't parse or user declined the parsed title, ask for name
    if not name:
        name = Prompt.ask("Enter show name")
    
    # Create and save the show
    show = Show(name=name, url=url)
    
    # Check if show already exists by URL
    existing_show = db.get_show_by_url(url)
    
    # Initialize show_id variable
    show_id = None
    
    if existing_show:
        console.print(f"[yellow]Show with this URL already exists (ID: {existing_show.id}, Name: {existing_show.name})[/yellow]")
        show_id = existing_show.id
        
        # Ask if user wants to update the name
        if name != existing_show.name and name:
            update_name = Confirm.ask(f"Update name from '{existing_show.name}' to '{name}'?", default=True)
            if update_name:
                existing_show.name = name
                db.update_show(existing_show)
                console.print(f"[green]Updated show name to: {name}[/green]")
    else:
        # Add the new show and get its ID
        show_id = db.add_show(show)
        console.print(f"[green]Added show with ID: {show_id}[/green]")
    
    # If we have episode data, proceed to add episodes
    if feed_data and 'episodes' in feed_data and feed_data['episodes']:
        console.print(f"[green]Found {len(feed_data['episodes'])} episodes[/green]")
        
        # Define valid options and provide validation
        valid_episode_options = ["all", "single", "range"]
        
        # Ask for episode range
        while True:
            episode_input = Prompt.ask(
                "Enter episode number(s) to add (empty for all, number for single, range for selecting a range)",
                default="all"
            )
            
            # Check if input is directly a number
            if episode_input.isdigit():
                console.print(f"[green]Selected episode {episode_input}[/green]")
                break
                
            # Validate input against known options
            if episode_input.lower() not in valid_episode_options:
                console.print(f"[red]Invalid input: '{episode_input}'. Please enter 'all', 'single', 'range', or a specific number.[/red]")
                continue
            else:
                break
        
        # Handle special case for "single" input
        if episode_input.lower() == "single":
            # Prompt for a specific episode number
            episode_number = Prompt.ask("Enter the specific episode number to add", default="1")
            try:
                # Convert to integer (1-indexed)
                episode_num = int(episode_number)
                episode_input = str(episode_num)
                console.print(f"[green]Selected episode {episode_input}[/green]")
            except ValueError:
                console.print("[red]Invalid episode number. Using default (all episodes)[/red]")
                episode_input = "all"
                
        # Handle special case for "range" input
        elif episode_input.lower() == "range":
            # Show examples for range input
            console.print("[yellow]Examples:[/yellow]")
            console.print("  - Single range: [cyan]1-5[/cyan]")
            console.print("  - Multiple ranges: [cyan]1-5,10-15,20[/cyan]")
            console.print("  - Individual episodes: [cyan]3,7,9[/cyan]")
            
            # Get the range input directly
            episode_input = Prompt.ask("Enter episode range", default="1-10")
            
            # Check if the range is valid
            episode_indices = parse_episode_range(episode_input)
            
            if not episode_indices and episode_input.lower() != "all":
                console.print("[red]Invalid range format. Using default (all episodes)[/red]")
                episode_input = "all"
            else:
                episode_desc = get_episode_description(episode_indices)
                console.print(f"[green]Selected {episode_desc}[/green]")
        
        # For any other value (including "all"), parse the episode range
        episode_range = parse_episode_range(episode_input)
        episode_desc = get_episode_description(episode_range) if episode_range else "all episodes"
        console.print(f"[yellow]Adding {episode_desc}...[/yellow]")
        
        # Filter episodes if a specific range was requested
        episodes_to_add = feed_data['episodes']
        if episode_range:
            filtered_episodes = []
            for i, episode in enumerate(episodes_to_add):
                # We're 0-indexed internally, but user-facing is 1-indexed
                user_facing_index = i + 1
                if user_facing_index in episode_range:
                    filtered_episodes.append(episode)
            episodes_to_add = filtered_episodes
        
        # Add each episode to the database
        with Progress() as progress:
            task = progress.add_task("[cyan]Adding episodes...", total=len(episodes_to_add))
            
            for episode_idx, episode_data in enumerate(episodes_to_add, 1):
                title = episode_data.get('title', f"Episode {episode_idx}")
                url = episode_data.get('url', '')
                published = episode_data.get('published_at')
                
                # Generate a hash for the episode
                import hashlib
                # Use either the episode number from the data, or the episode index as fallback
                ep_num = episode_data.get('episode_number', str(episode_idx))
                hash_input = f"{show_id}_{ep_num}_{url}"
                file_hash = hashlib.md5(hash_input.encode()).hexdigest()
                
                # Create the episode
                episode = Episode(
                    show_id=show_id,
                    title=title,
                    url=url,
                    episode_number=ep_num,
                    published_at=published,  # Use the parsed datetime object
                    file_hash=file_hash  # Store the hash even before downloading
                )
                
                # Save it
                db.add_episode(episode)
                progress.update(task, advance=1)
        
        console.print(f"[green]Added {len(episodes_to_add)} episodes[/green]")
        
        # Always download episodes automatically without prompting
        console.print(f"[yellow]Starting download for show ID {show_id}...[/yellow]")
        download_episodes(show_id, episode_input, skip_reindex=True)

@list_app.command("downloads")
def list_downloads(show_id: Optional[int] = typer.Argument(None)):
    """List all downloaded files for a show with their corresponding episodes"""
    # If no show_id provided, prompt user to select one
    if show_id is None:
        try:
            show_id = prompt_for_show_id()
        except typer.Exit:
            # If the user doesn't have any shows, just show a message and exit
            console.print("[yellow]No shows available. Add a show first using 'parchive add-show'[/yellow]")
            raise typer.Exit()
    
    # Get the show
    show = db.get_show(show_id)
    if not show:
        console.print(f"[red]Show with ID {show_id} not found[/red]")
        return
    
    # Get episodes
    episodes = db.list_episodes(show_id)
    
    if not episodes:
        console.print(f"[yellow]No episodes found for show: {show.name}[/yellow]")
        return
    
    # Get the download directory
    download_dir = Path(f"downloads/{show_id}")
    
    if not download_dir.exists():
        console.print(f"[yellow]No download directory found for show: {show.name} (ID: {show_id})[/yellow]")
        return
    
    # Count files
    all_files = list(download_dir.glob("*.*"))
    if not all_files:
        console.print(f"[yellow]No downloaded files found for show: {show.name} (ID: {show_id})[/yellow]")
        return
    
    # Define special files that should be excluded from the main listing
    special_files = ['cover.jpg', 'metadata.json', 'feed.xml']
    
    # Display episodes with downloads
    console.print(f"[bold]Downloads for {show.name}:[/bold]")
    
    # First display special files separately
    for special_file in special_files:
        file_path = download_dir / special_file
        if file_path.exists():
            file_size = file_path.stat().st_size
            file_size_str = f"{file_size / 1024:.2f} KB"
            if special_file == 'feed.xml':
                console.print(f"[blue]Found RSS feed archive: {special_file} ({file_size_str})[/blue]")
            elif special_file == 'cover.jpg':
                console.print(f"[blue]Found show cover image: {special_file} ({file_size_str})[/blue]")
            elif special_file == 'metadata.json':
                console.print(f"[blue]Found show metadata: {special_file} ({file_size_str})[/blue]")
    
    downloads_table = Table(show_header=True, header_style="bold magenta")
    downloads_table.add_column("Filename", style="dim")
    downloads_table.add_column("Episode")
    downloads_table.add_column("Title")
    downloads_table.add_column("Size", style="dim")
    
    # Track which episodes are downloaded
    downloaded_episodes = []
    
    for file_path in all_files:
        # Skip special files - they're displayed separately
        if file_path.name in special_files:
            continue
            
        # Parse the filename to get the hash part
        # Filename format is "episode_number_hash.extension"
        filename_parts = file_path.stem.split('_', 1)
        
        # If there's only one part, assume it's all hash (for backward compatibility)
        if len(filename_parts) == 1:
            file_hash = filename_parts[0]
        else:
            file_hash = filename_parts[1]  # The part after the first underscore
        
        # Find the matching episode
        matching_episode = None
        for episode in episodes:
            if episode.file_hash and episode.file_hash == file_hash:
                matching_episode = episode
                downloaded_episodes.append(episode.id)
                break
        
        # Calculate file size
        file_size = file_path.stat().st_size
        size_str = f"{file_size / 1024 / 1024:.2f} MB"
        
        # Add to table
        downloads_table.add_row(
            file_path.name,
            matching_episode.episode_number if matching_episode else "Unknown",
            matching_episode.title if matching_episode else "Unknown",
            size_str
        )
    
    console.print(downloads_table)
    
    # Show summary - exclude special files from count
    episode_files = len([f for f in all_files if f.name not in special_files])
    
    console.print(f"[green]Found {episode_files} downloaded episode files[/green]")
    console.print(f"[green]{len(downloaded_episodes)} of {len(episodes)} episodes downloaded[/green]")

def download_rss_feed(show_url: str, output_path: Path) -> bool:
    """Download and save a copy of the show's RSS feed
    
    Args:
        show_url: URL of the show's RSS feed
        output_path: Path to save the RSS feed
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        import requests
        response = requests.get(show_url, timeout=30)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            f.write(response.content)
            
        return True
    except Exception as e:
        console.print(f"[red]Error downloading RSS feed: {str(e)}[/red]")
        return False

def mark_deleted(
    show_id: Optional[int] = typer.Argument(None, help="ID of the show"),
    episode_number: Optional[str] = typer.Argument(None, help="Episode number to mark as deleted")
):
    """Mark an episode as deleted (when the file has been deleted manually)"""
    # If no show_id provided, prompt user to select one
    if show_id is None:
        show_id = prompt_for_show_id()
        
    # Get the show
    show = db.get_show(show_id)
    if not show:
        console.print(f"[red]Show with ID {show_id} not found[/red]")
        return
    
    # If no episode_number provided, list episodes and prompt for one
    if episode_number is None:
        # List the episodes for the selected show
        episodes_list = db.list_episodes(show_id)
        
        if not episodes_list:
            console.print(f"[yellow]No episodes found for show: {show.name}[/yellow]")
            return
            
        # Display available episodes
        episode_table = Table(show_header=True, header_style="bold magenta")
        episode_table.add_column("Number")
        episode_table.add_column("Title")
        episode_table.add_column("Status", style="dim")
        
        for episode in episodes_list:
            # Determine status
            if episode.is_downloaded:
                status = "[green]Downloaded[/green]"
            elif episode.was_downloaded:
                status = "[yellow]Deleted[/yellow]"
            else:
                status = "[dim]Not downloaded[/dim]"
                
            episode_table.add_row(
                episode.episode_number,
                episode.title,
                status
            )
        
        console.print(f"[bold]Episodes for {show.name}:[/bold]")
        console.print(episode_table)
        
        # Prompt for episode number
        episode_number = Prompt.ask("Enter the number of the episode to mark as deleted")
    
    # Find the episode with matching episode_number
    episode = None
    episodes = db.list_episodes(show_id)
    for ep in episodes:
        if ep.episode_number == episode_number:
            episode = ep
            break
    
    # Check if episode was found
    if not episode:
        console.print(f"[red]Episode number {episode_number} not found for show: {show.name}[/red]")
        return
        
    # Check that the episode belongs to the show
    if episode.show_id != show_id:
        console.print(f"[red]Episode {episode_number} does not belong to show {show_id}[/red]")
        return
        
    # Check if it's already marked as deleted
    if not episode.is_downloaded:
        console.print(f"[yellow]Episode '{episode.title}' is already marked as not downloaded[/yellow]")
        return
        
    # Update the status
    if db.update_episode_download_status(episode.id, False):
        console.print(f"[green]Episode '{episode.title}' marked as deleted[/green]")
    else:
        console.print(f"[red]Failed to update episode status[/red]")

@app.command()
def reindex(
    show_id: Optional[int] = typer.Argument(None, help="ID of the show to reindex"),
    force: bool = typer.Option(False, "--force", "-f", help="Force reindex without prompting")
):
    """Reindex a show's episodes from the RSS feed and compare with existing database entries"""
    # If no show_id provided, prompt user to select one
    if show_id is None:
        try:
            show_id = prompt_for_show_id()
        except typer.Exit:
            # If the user doesn't have any shows, just show a message and exit
            console.print("[yellow]No shows available. Add a show first using 'parchive add-show'[/yellow]")
            raise typer.Exit()
    
    # Get the show
    show = db.get_show(show_id)
    if not show:
        console.print(f"[red]Show with ID {show_id} not found[/red]")
        return
    
    # Get existing episodes from database
    db_episodes = db.list_episodes(show_id)
    console.print(f"[yellow]Found {len(db_episodes)} episodes in database for '{show.name}'[/yellow]")
    
    # Parse RSS feed
    console.print(f"[yellow]Fetching feed: {show.name}[/yellow]")
    feed_data = parse_rss_feed(show.url)
    
    if not feed_data or 'episodes' not in feed_data or not feed_data['episodes']:
        console.print("[red]No episodes found in feed[/red]")
        return
    
    console.print(f"[yellow]Found {len(feed_data['episodes'])} episodes in RSS feed[/yellow]")
    
    # Process feed episodes for comparison
    feed_episodes = []
    for i, episode_data in enumerate(feed_data['episodes'], 1):
        title = episode_data.get('title', f"Episode {i}")
        url = episode_data.get('url', '')
        published = episode_data.get('published_at')
        
        # Try to extract episode number from title
        episode_number = str(i)
        import re
        match = re.match(r'^(\d+)[\s:\-\.]+', title)
        if match:
            episode_number = match.group(1)
        
        feed_episodes.append({
            'title': title,
            'url': url,
            'episode_number': episode_number,
            'published_at': published
        })
    
    # Compare episodes by URL (primary key for matching)
    db_urls = {episode.url: episode for episode in db_episodes}
    feed_urls = {episode['url']: episode for episode in feed_episodes}
    

    
    # Find differences
    new_episodes = [ep for url, ep in feed_urls.items() if url not in db_urls]
    missing_episodes = [ep for url, ep in db_urls.items() if url not in feed_urls]
    

    
    # Check for modified episodes (same URL but different title or episode number)
    modified_episodes = []
    for url, feed_ep in feed_urls.items():
        if url in db_urls:
            db_ep = db_urls[url]
            if feed_ep['title'] != db_ep.title or feed_ep['episode_number'] != db_ep.episode_number:
                modified_episodes.append({
                    'feed': feed_ep,
                    'db': db_ep
                })
    
    # Display differences
    has_differences = new_episodes or missing_episodes or modified_episodes
    
    if not has_differences:
        console.print("[green]No differences found between database and RSS feed[/green]")
        return
        
    # Create tables for each type of difference
    console.print("\n[bold]Differences between database and RSS feed:[/bold]")
    
    # Display new episodes in a table
    if new_episodes:
        new_table = Table(show_header=True, header_style="bold green")
        new_table.add_column("Number", style="dim")
        new_table.add_column("Title")
        new_table.add_column("Published", style="dim")
        new_table.add_column("Status", style="green")
        
        for i, ep in enumerate(new_episodes[:10], 1):  # Show first 10
            try:
                published = ep['published_at'].strftime("%Y-%m-%d") if ep['published_at'] else "Unknown"
            except (AttributeError, TypeError):
                # Handle case where published_at is not a datetime object
                published = str(ep['published_at']) if ep['published_at'] else "Unknown"
                
            new_table.add_row(
                ep['episode_number'],
                ep['title'],
                published,
                "[green]NEW[/green]"
            )
            
        console.print(f"\n[bold green]New episodes in feed ({len(new_episodes)}):[/bold green]")
        console.print(new_table)
        
        # If more than 10, show how many more
        if len(new_episodes) > 10:
            console.print(f"[dim]...and {len(new_episodes) - 10} more new episodes[/dim]")
    
    # Display missing episodes in a table
    if missing_episodes:
        missing_table = Table(show_header=True, header_style="bold red")
        missing_table.add_column("Number", style="dim")
        missing_table.add_column("Title")
        missing_table.add_column("Status", style="red")
        missing_table.add_column("Downloaded", style="dim")
        
        for i, ep in enumerate(missing_episodes, 1):
            # Determine download status text
            if ep.is_downloaded:
                dl_status = ep.download_date.strftime("%Y-%m-%d") if ep.download_date else "Yes"
    else:
                dl_status = ""
                
                missing_table.add_row(
                ep.episode_number,
                ep.title,
                "[red]REMOVED[/red]",
                dl_status
            )
            
    console.print(f"\n[bold red]Episodes in database but missing from feed ({len(missing_episodes)}):[/bold red]")
    console.print(missing_table)
    
    # Display modified episodes in a table
    if modified_episodes:
        modified_table = Table(show_header=True, header_style="bold yellow")
        modified_table.add_column("Number", style="dim")
        modified_table.add_column("Database Title")
        modified_table.add_column("Feed Title")
        modified_table.add_column("Changes", style="yellow")
        
        for i, ep in enumerate(modified_episodes, 1):
            feed_ep = ep['feed']
            db_ep = ep['db']
            
            # Identify what changed
            changes = []
            if feed_ep['title'] != db_ep.title:
                changes.append("title")
            if feed_ep['episode_number'] != db_ep.episode_number:
                changes.append("number")
            if feed_ep['published_at'] != db_ep.published_at:
                changes.append("date")
                
            modified_table.add_row(
                f"{db_ep.episode_number} → {feed_ep['episode_number']}" if db_ep.episode_number != feed_ep['episode_number'] else db_ep.episode_number,
                db_ep.title,
                feed_ep['title'],
                ", ".join(changes)
            )
            
        console.print(f"\n[bold yellow]Modified episodes ({len(modified_episodes)}):[/bold yellow]")
        console.print(modified_table)
    
    # Prompt for confirmation
    if not force:
        proceed = Confirm.ask("\nDifferences found. Update database with feed data?")
        if not proceed:
            console.print("[yellow]Reindex cancelled[/yellow]")
            return
    
    # Perform the update
    with Progress() as progress:
        task = progress.add_task("[cyan]Updating episodes...", total=len(feed_episodes))
        
        for episode_data in feed_episodes:
            title = episode_data['title']
            url = episode_data['url']
            episode_number = episode_data['episode_number']
            published_at = episode_data['published_at']
            
            # Check if episode already exists in database
            existing_episode = None
            for db_ep in db_episodes:
                if db_ep.url == url:
                    existing_episode = db_ep
                    break
            
            if existing_episode:
                # Update existing episode
                existing_episode.title = title
                existing_episode.episode_number = episode_number
                existing_episode.published_at = published_at
                db.update_episode(existing_episode)
            else:
                # Create new episode
                new_ep = Episode(
                    show_id=show_id,
                    title=title,
                    url=url,
                    episode_number=episode_number,
                    published_at=published_at
                )
                db.add_episode(new_ep)
            
            progress.update(task, advance=1)
    
    console.print(f"[green]Successfully reindexed {len(feed_episodes)} episodes for '{show.name}'[/green]")

@app.command()
def scan(
    show_id: Optional[int] = typer.Argument(None, help="ID of the show to scan"),
    fix: bool = typer.Option(False, "--fix", "-f", help="Fix database/filesystem mismatches"),
    force: bool = typer.Option(False, "--force", help="Force delete orphaned files without matching database entries")
):
    """Scan for database/filesystem mismatches and optionally fix them"""
    # If no show_id provided, prompt user to select one or scan all shows
    if show_id is None:
        scan_all = Confirm.ask("Scan all shows?", default=True)
        if not scan_all:
            try:
                show_id = prompt_for_show_id()
            except typer.Exit:
                console.print("[yellow]No shows found in the database. Add a show first.[/yellow]")
                return
        else:
            shows = db.list_shows()
            if not shows:
                console.print("[yellow]No shows found in the database.[/yellow]")
            return
    
    # Scan the specific show
    scan_show(show_id, fix, force)

def scan_show(show_id: int, fix: bool = False, force: bool = False):
    """Scan a show for database/filesystem mismatches and fix them if requested"""
    # Get show from database
    show = db.get_show(show_id)
    if not show:
        console.print(f"[red]Show {show_id} not found[/red]")
        return
        
    console.print(f"[bold]Scanning show: {show.name} (ID: {show_id})[/bold]")
    
    # Get all episodes from database
    episodes = db.list_episodes(show_id)
    if not episodes:
        console.print(f"[yellow]No episodes found in database for: {show.name}[/yellow]")
        return
        
    # Check download directory
    download_dir = Path(f"downloads/{show_id}")
    if not download_dir.exists():
        console.print(f"[yellow]No download directory exists for: {show.name}[/yellow]")
        
        # Mark all episodes as not downloaded if fix is enabled
        if fix:
            fixed_count = 0
            for episode in episodes:
                if episode.is_downloaded:
                    if db.update_episode_download_status(episode.id, False):
                        fixed_count += 1
            
            if fixed_count > 0:
                console.print(f"[green]Fixed {fixed_count} episodes marked as downloaded but missing files[/green]")
        return
    
    # Get all audio files in the directory
    audio_files = list(download_dir.glob('*.mp3'))
    image_files = list(download_dir.glob('*.jpg'))
    
    # Exclude special files: cover.jpg, feed.xml, metadata.json
    special_files = ['cover.jpg', 'feed.xml', 'metadata.json']
    all_media_files = audio_files + [f for f in image_files if f.name not in special_files]
    
    if not all_media_files:
        console.print(f"[yellow]No media files found in download directory for: {show.name}[/yellow]")
        
        # Mark all episodes as not downloaded if fix is enabled
        if fix:
            fixed_count = 0
            for episode in episodes:
                if episode.is_downloaded:
                    if db.update_episode_download_status(episode.id, False):
                        fixed_count += 1
            
            if fixed_count > 0:
                console.print(f"[green]Fixed {fixed_count} episodes marked as downloaded but missing files[/green]")
        return
    
    # Create a mapping from file hash to files on disk
    file_hash_map = {}
    for file_path in all_media_files:
        # Parse the filename to get the hash part
        # Filename format is "episode_number_hash.extension"
        filename_parts = file_path.stem.split('_', 1)
        
        # If there's only one part, assume it's all hash (for backward compatibility)
        if len(filename_parts) == 1:
            file_hash = filename_parts[0]
        else:
            file_hash = filename_parts[1]  # The part after the first underscore
            
        if file_hash not in file_hash_map:
            file_hash_map[file_hash] = []
        file_hash_map[file_hash].append(file_path)
    
    # Check for mismatches
    mismatches = []
    
    # Case 1: Episode marked as downloaded but file missing
    missing_files = []
    for episode in episodes:
        if episode.is_downloaded and episode.file_hash and episode.file_hash not in file_hash_map:
            missing_files.append(episode)
    
    # Case 2: File exists but episode not marked as downloaded
    missing_database = []
    for file_hash, file_paths in file_hash_map.items():
        for episode in episodes:
            if ((episode.file_hash == file_hash) or (episode.image_file_hash == file_hash)) and not episode.is_downloaded:
                missing_database.append((episode, file_paths))
                break
    
    # Case 3: File exists but no matching episode in database
    orphaned_files = []
    for file_hash, file_paths in file_hash_map.items():
        if not any((episode.file_hash == file_hash) or (episode.image_file_hash == file_hash) for episode in episodes):
            orphaned_files.extend(file_paths)
    
    # Report mismatches
    console.print(f"[yellow]Found {len(missing_files)} episodes marked as downloaded but missing files[/yellow]")
    console.print(f"[yellow]Found {len(missing_database)} files not marked as downloaded in database[/yellow]")
    console.print(f"[yellow]Found {len(orphaned_files)} orphaned files (no matching episode in database)[/yellow]")
    
    # Fix mismatches if requested
    if fix or force:
        fixed_count = 0
        
        # Fix Case 1: Mark episodes with missing files as not downloaded
        if fix:
            for episode in missing_files:
                if db.update_episode_download_status(episode.id, False):
                    fixed_count += 1
                    console.print(f"[green]Marked episode {episode.title} (Number: {episode.episode_number}) as not downloaded[/green]")
            
            # Fix Case 2: Mark episodes with existing files as downloaded
            for episode, file_paths in missing_database:
                if db.update_episode_download_status(episode.id, True, episode.file_hash):
                    fixed_count += 1
                    console.print(f"[green]Marked episode {episode.title} (Number: {episode.episode_number}) as downloaded[/green]")
        
        # Fix Case 3: Delete orphaned files if force is enabled
        if force and orphaned_files:
            deleted_count = 0
            console.print("[yellow]Deleting orphaned files:[/yellow]")
            for file_path in orphaned_files:
                try:
                    file_path.unlink()
                    deleted_count += 1
                    console.print(f"[green]Deleted orphaned file: {file_path.name}[/green]")
                except Exception as e:
                    console.print(f"[red]Error deleting {file_path.name}: {str(e)}[/red]")
            
            if deleted_count > 0:
                console.print(f"[green]Deleted {deleted_count} orphaned files[/green]")
                fixed_count += deleted_count
        elif orphaned_files:
            console.print("[yellow]Orphaned files found but not deleted. Use --force to delete them:[/yellow]")
            for file_path in orphaned_files:
                console.print(f"  - {file_path.name}")
        
        if fixed_count > 0:
            console.print(f"[green]Fixed {fixed_count} database/filesystem mismatches[/green]")
        else:
            console.print("[yellow]No fixable mismatches found[/yellow]")
    elif missing_files or missing_database or orphaned_files:
        console.print("[cyan]Run with --fix to resolve database mismatches[/cyan]")
        console.print("[cyan]Run with --force to delete orphaned files[/cyan]")

if __name__ == "__main__":
    app()
