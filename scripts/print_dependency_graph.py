#!/usr/bin/env python3
"""Print the full pipeline dependency graph."""

import sys
from collections import defaultdict
from pathlib import Path

import click


sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tag_data_engineering.pipeline.pipeline_discoverer import PipelineDiscoverer


def build_dependency_graph(pipeline):
    """Build adjacency list representation of the dependency graph."""
    graph = {}
    reverse_graph = defaultdict(list)

    for activity in pipeline.activities:
        graph[activity.name] = activity.dependencies
        for dep in activity.dependencies:
            reverse_graph[dep].append(activity.name)

    return graph, reverse_graph


def compute_stats(pipeline, graph, reverse_graph):
    """Compute statistics about the pipeline."""
    layer_counts = defaultdict(int)
    for activity in pipeline.activities:
        layer_counts[activity.layer.value] += 1

    roots = [name for name, deps in graph.items() if not deps]
    leaves = [name for name in graph if name not in reverse_graph]

    def get_depth(name, memo=None):
        if name in memo:
            return memo[name]
        deps = graph.get(name, [])
        if not deps:
            memo[name] = 0
            return 0
        depth = 1 + max(get_depth(d, memo) for d in deps if d in graph)
        memo[name] = depth
        return depth

    depths = {name: get_depth(name) for name in graph}
    max_depth = max(depths.values()) if depths else 0

    depth_levels = defaultdict(list)
    for name, depth in depths.items():
        depth_levels[depth].append(name)

    max_width = max(len(v) for v in depth_levels.values()) if depth_levels else 0
    widest_level = [k for k, v in depth_levels.items() if len(v) == max_width][0] if depth_levels else 0

    return {
        "total_activities": len(pipeline.activities),
        "layer_counts": dict(layer_counts),
        "roots": roots,
        "leaves": leaves,
        "max_depth": max_depth,
        "max_width": max_width,
        "widest_level": widest_level,
        "depth_levels": {k: len(v) for k, v in sorted(depth_levels.items())},
    }


def print_text_format(pipeline, graph, reverse_graph, show_stats=False):
    """Print human-readable text format."""
    if show_stats:
        stats = compute_stats(pipeline, graph, reverse_graph)
        click.echo("=" * 60)
        click.echo("PIPELINE STATISTICS")
        click.echo("=" * 60)
        click.echo(f"Total activities: {stats['total_activities']}")
        click.echo(f"Max depth (critical path): {stats['max_depth']}")
        click.echo(f"Max width (parallelism): {stats['max_width']} at depth {stats['widest_level']}")
        click.echo()
        click.echo("Activities per layer:")
        for layer, count in sorted(stats["layer_counts"].items()):
            click.echo(f"  {layer}: {count}")
        click.echo()
        click.echo("Activities per depth level:")
        for depth, count in stats["depth_levels"].items():
            click.echo(f"  Depth {depth}: {count} activities")
        click.echo()
        click.echo(f"Root activities (no dependencies): {len(stats['roots'])}")
        click.echo(f"Leaf activities (nothing depends on them): {len(stats['leaves'])}")
        click.echo()

    click.echo("=" * 60)
    click.echo("DEPENDENCY GRAPH")
    click.echo("=" * 60)

    current_layer = None
    for activity in pipeline.activities:
        if activity.layer != current_layer:
            current_layer = activity.layer
            click.echo(f"\n[{current_layer.value.upper()}]")
            click.echo("-" * 40)

        deps_str = ", ".join(activity.dependencies) if activity.dependencies else "(none)"
        dependents = reverse_graph.get(activity.name, [])
        dependents_str = ", ".join(dependents) if dependents else "(none)"

        click.echo(f"\n  {activity.name}")
        click.echo(f"    ← depends on: {deps_str}")
        click.echo(f"    → depended by: {dependents_str}")


def print_mermaid_format(pipeline, graph, reverse_graph):
    """Print Mermaid flowchart format with improved styling."""
    click.echo("```mermaid")
    click.echo("%%{init: {'theme': 'base', 'themeVariables': {'fontSize': '12px'}}}%%")
    click.echo("flowchart LR")
    click.echo()

    # Layer colors and shapes
    layer_styles = {
        "setup": ("setup", "([", "])", "#e1f5fe"),
        "landing": ("land", "[[", "]]", "#fff3e0"),
        "landing_copyjob": ("lcj", "{{", "}}", "#fff3e0"),
        "landing_copyjob_normalize": ("lcjn", "[[", "]]", "#fff3e0"),
        "bronze": ("brz", "[", "]", "#fce4ec"),
        "silver": ("slv", "[/", "/]", "#e8f5e9"),
        "gold": ("gld", "[(", ")]", "#fff9c4"),
    }

    # Group activities by layer
    layer_activities = defaultdict(list)
    for activity in pipeline.activities:
        layer_activities[activity.layer.value].append(activity)

    # Define subgraphs with styling
    layer_order = ["setup", "landing", "landing_copyjob", "landing_copyjob_normalize", "bronze", "silver", "gold"]

    for layer in layer_order:
        activities = layer_activities.get(layer, [])
        if not activities:
            continue

        prefix, shape_l, shape_r, color = layer_styles[layer]

        click.echo(f"    subgraph {layer.upper().replace('_', ' ')}")
        click.echo("        direction TB")
        for activity in activities:
            node_id = activity.name
            # Create short label: just the entity name
            label = activity.entity
            click.echo(f'        {node_id}{shape_l}"{label}"{shape_r}')
        click.echo("    end")
        click.echo()

    # Add edges (only between different layers to reduce clutter)
    click.echo("    %% Dependencies")
    for activity in pipeline.activities:
        for dep in activity.dependencies:
            if dep in graph:
                click.echo(f"    {dep} --> {activity.name}")

    click.echo()

    # Add style classes
    # click.echo("    %% Styling")
    # for layer in layer_order:
    #     activities = layer_activities.get(layer, [])
    #     if not activities:
    #         continue
    #     _, _, _, color = layer_styles[layer]
    #     node_ids = " & ".join(a.name for a in activities)
    #     if node_ids:
    #         click.echo(f"    style {node_ids} fill:{color}")

    click.echo("```")


@click.command()
@click.option("--format", "-f", "output_format", type=click.Choice(["text", "mermaid"]), default="text", help="Output format")
@click.option("--stats", "-s", is_flag=True, help="Include statistics (text format only)")
def main(output_format: str, stats: bool):
    """Print the pipeline dependency graph."""
    discoverer = PipelineDiscoverer()
    pipeline = discoverer.build_pipeline("analysis")
    graph, reverse_graph = build_dependency_graph(pipeline)

    if output_format == "text":
        print_text_format(pipeline, graph, reverse_graph, stats)
    elif output_format == "mermaid":
        print_mermaid_format(pipeline, graph, reverse_graph)


if __name__ == "__main__":
    main()
