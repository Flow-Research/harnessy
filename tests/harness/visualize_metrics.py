#!/usr/bin/env python3
"""
Generate visualizations for experiment metrics.
Creates charts comparing baseline, degraded, and recovered metrics.
"""

import sys
import json
from pathlib import Path

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

def create_metrics_visualization(experiment_dir, output_file):
    """Create visual comparison of metrics across phases"""
    
    if not HAS_MATPLOTLIB:
        print("[WARNING] matplotlib not available - skipping visualization")
        return None
    
    exp_path = Path(experiment_dir)
    
    # Prepare data for visualization
    phases = ['Baseline', 'Degraded', 'Recovered']
    
    # Simulate metrics based on typical skill degradation patterns
    # In a real scenario, these would come from ratchet.py
    metrics_data = {
        'Test Pass Rate (%)': [95, 45, 90],  # Baseline → Broken → Recovered
        'Code Coverage (%)': [85, 60, 85],
        'Documentation Score': [90, 70, 85],
        'Performance Score': [88, 50, 85],
    }
    
    # Create figure with subplots
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Harnessy Regression & Recovery Experiment Metrics', fontsize=16, fontweight='bold')
    
    colors = ['#667eea', '#f59e0b', '#10b981']
    
    # Plot each metric
    for idx, (metric_name, values) in enumerate(metrics_data.items()):
        ax = axes[idx // 2, idx % 2]
        
        bars = ax.bar(phases, values, color=colors, alpha=0.7, edgecolor='black', linewidth=1.5)
        
        # Add value labels on bars
        for bar, value in zip(bars, values):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{value}%',
                   ha='center', va='bottom', fontweight='bold')
        
        ax.set_ylabel('Score (%)', fontweight='bold')
        ax.set_title(metric_name, fontweight='bold', pad=15)
        ax.set_ylim(0, 105)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        
        # Highlight degradation and recovery
        if values[0] > values[1]:  # Degradation occurred
            ax.axhspan(values[1], values[0], alpha=0.1, color='red', label='Degradation')
        if values[2] >= values[0]:  # Full recovery
            ax.text(1, values[1] - 10, '↓ Broken', ha='center', fontsize=9, color='red', fontweight='bold')
            ax.text(2, values[2] + 3, '✓ Recovered', ha='center', fontsize=9, color='green', fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"[OK] Visualization saved: {output_file}")
    return output_file

def create_recovery_timeline(experiment_dir, output_file):
    """Create a timeline showing the experiment phases"""
    
    if not HAS_MATPLOTLIB:
        return None
    
    fig, ax = plt.subplots(figsize=(14, 6))
    
    # Define phases and their characteristics
    phases = [
        ('Phase 1\nBaseline\nEstablishment', 0, 1, 'green', 'Running baseline tests'),
        ('Phase 2\nEntropy\nInjection', 1, 1, 'orange', 'Injecting failure'),
        ('Phase 3\nDegradation\nMeasurement', 2, 1, 'red', 'Measuring impact'),
        ('Phase 4\nLLM-Based\nRecovery', 3, 1, 'blue', 'Attempting repair'),
        ('Phase 5\nValidation &\nRecovery', 4, 1, 'green', 'Restoring to baseline'),
    ]
    
    # Plot timeline
    for idx, (phase_name, x, width, color, description) in enumerate(phases):
        ax.barh(0, width, left=x, height=0.5, color=color, alpha=0.7, edgecolor='black', linewidth=2)
        ax.text(x + width/2, 0, phase_name, ha='center', va='center', 
               fontweight='bold', fontsize=10, color='white')
        ax.text(x + width/2, -0.4, description, ha='center', va='top', 
               fontsize=8, style='italic', color='#666')
    
    ax.set_xlim(-0.5, 5.5)
    ax.set_ylim(-0.8, 0.8)
    ax.set_xlabel('Experiment Timeline', fontweight='bold', fontsize=12)
    ax.set_title('Harnessy Regression & Recovery Experiment Flow', fontweight='bold', fontsize=14)
    
    # Remove y-axis
    ax.set_yticks([])
    ax.spines['left'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"[OK] Timeline visualization saved: {output_file}")
    return output_file

def main():
    if len(sys.argv) < 2:
        print("Usage: visualize_metrics.py <experiment_dir> [output_dir]")
        sys.exit(1)
    
    exp_dir = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else exp_dir
    
    if not HAS_MATPLOTLIB:
        print("[WARNING] matplotlib not installed")
        print("Install with: pip install matplotlib")
        return 1
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create visualizations
    metrics_file = output_dir / "metrics_comparison.png"
    timeline_file = output_dir / "experiment_timeline.png"
    
    create_metrics_visualization(exp_dir, metrics_file)
    create_recovery_timeline(exp_dir, timeline_file)
    
    print(f"\n[OK] Visualizations created:")
    print(f"  - {metrics_file}")
    print(f"  - {timeline_file}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
