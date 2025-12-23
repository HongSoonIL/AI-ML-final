"""
학습 데이터 분석 및 통계 생성 스크립트

이 스크립트는 학습 데이터의 통계 정보를 생성하고 시각화합니다.
- 데이터셋 크기 및 구성
- 입력/정답 데이터 분포
- 높이 보정 효과 분석
"""

import os
import sys
import numpy as np
import matplotlib.pyplot as plt
from glob import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

PROCESSED_DIR = os.path.join(ROOT, "data", "processed")
OUTPUT_DIR = os.path.join(ROOT, "docs", "data_analysis")

os.makedirs(OUTPUT_DIR, exist_ok=True)


def analyze_dataset():
    """
    학습 데이터셋의 전체 통계를 분석합니다.
    
    Returns:
        dict: 데이터셋 통계 정보
    """
    raw_files = sorted(glob(f"{PROCESSED_DIR}/*_raw.npy"))
    target_files = sorted(glob(f"{PROCESSED_DIR}/*_target.npy"))
    
    stats = {
        "num_videos": len(raw_files),
        "video_names": [],
        "total_frames": 0,
        "frames_per_video": [],
        "input_dim": 99,  # 33 keypoints × 3 coordinates
        "output_dim": 99,
        "num_keypoints": 33,
    }
    
    print("=" * 80)
    print("Dataset Analysis")
    print("=" * 80)
    
    for raw_path, target_path in zip(raw_files, target_files):
        video_name = os.path.basename(raw_path).replace("_raw.npy", "")
        raw_data = np.load(raw_path)  # (T, 33, 3)
        target_data = np.load(target_path)  # (T, 33, 3)
        
        num_frames = len(raw_data)
        
        stats["video_names"].append(video_name)
        stats["total_frames"] += num_frames
        stats["frames_per_video"].append(num_frames)
        
        print(f"\nVideo: {video_name}")
        print(f"  - Number of frames: {num_frames:,}")
        print(f"  - Input shape: {raw_data.shape}")
        print(f"  - Target shape: {target_data.shape}")
        print(f"  - Flattened: ({num_frames}, 99)")
    
    print("\n" + "=" * 80)
    print("Overall Statistics")
    print("=" * 80)
    print(f"Total videos: {stats['num_videos']}")
    print(f"Total frames (samples): {stats['total_frames']:,}")
    print(f"Input dimension: {stats['input_dim']}")
    print(f"Output dimension: {stats['output_dim']}")
    print(f"Number of keypoints: {stats['num_keypoints']}")
    
    # Save statistics to file
    stats_path = os.path.join(OUTPUT_DIR, "dataset_stats.txt")
    with open(stats_path, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("Training Dataset Statistics\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Total videos: {stats['num_videos']}\n")
        f.write(f"Total frames: {stats['total_frames']:,}\n")
        f.write(f"Input dimension: {stats['input_dim']}\n")
        f.write(f"Output dimension: {stats['output_dim']}\n")
        f.write(f"Number of keypoints: {stats['num_keypoints']}\n\n")
        
        for i, video_name in enumerate(stats["video_names"]):
            f.write(f"\nVideo {i+1}: {video_name}\n")
            f.write(f"  Number of frames: {stats['frames_per_video'][i]:,}\n")
    
    print(f"\nStatistics saved: {stats_path}")
    
    return stats


def analyze_height_correction():
    """
    높이 보정의 효과를 분석합니다.
    
    입력 데이터와 정답 데이터를 비교하여:
    - 발의 최소 높이 (지면 레벨)
    - 전체 포즈의 높이 분포
    - 음수 높이의 개수
    """
    raw_files = sorted(glob(f"{PROCESSED_DIR}/*_raw.npy"))
    
    print("\n" + "=" * 80)
    print("Height Correction Effect Analysis")
    print("=" * 80)
    
    for raw_path in raw_files:
        target_path = raw_path.replace("_raw.npy", "_target.npy")
        video_name = os.path.basename(raw_path).replace("_raw.npy", "")
        
        raw_data = np.load(raw_path)  # (T, 33, 3)
        target_data = np.load(target_path)  # (T, 33, 3)
        
        # Y 좌표만 추출
        raw_y = raw_data[:, :, 1]  # (T, 33)
        target_y = target_data[:, :, 1]  # (T, 33)
        
        # BlazePose 발 키포인트 인덱스
        LEFT_FOOT = 31
        RIGHT_FOOT = 32
        
        # 발의 높이 분석
        raw_left_foot = raw_y[:, LEFT_FOOT]
        raw_right_foot = raw_y[:, RIGHT_FOOT]
        target_left_foot = target_y[:, LEFT_FOOT]
        target_right_foot = target_y[:, RIGHT_FOOT]
        
        print(f"\nVideo: {video_name}")
        print(f"\n  [Input Data - Raw BlazePose]")
        print(f"    Left foot height: min={raw_left_foot.min():.4f}, max={raw_left_foot.max():.4f}, mean={raw_left_foot.mean():.4f}")
        print(f"    Right foot height: min={raw_right_foot.min():.4f}, max={raw_right_foot.max():.4f}, mean={raw_right_foot.mean():.4f}")
        print(f"    All keypoints Y: min={raw_y.min():.4f}, max={raw_y.max():.4f}")
        print(f"    Negative height frames: {np.sum(raw_y < 0)} / {raw_y.size} ({100*np.sum(raw_y < 0)/raw_y.size:.2f}%)")
        
        print(f"\n  [Target Data - Height Corrected]")
        print(f"    Left foot height: min={target_left_foot.min():.4f}, max={target_left_foot.max():.4f}, mean={target_left_foot.mean():.4f}")
        print(f"    Right foot height: min={target_right_foot.min():.4f}, max={target_right_foot.max():.4f}, mean={target_right_foot.mean():.4f}")
        print(f"    All keypoints Y: min={target_y.min():.4f}, max={target_y.max():.4f}")
        print(f"    Negative height frames: {np.sum(target_y < 0)} / {target_y.size} ({100*np.sum(target_y < 0)/target_y.size:.2f}%)")
        
        # 시각화: 높이 분포 비교
        visualize_height_distribution(raw_y, target_y, video_name)


def visualize_height_distribution(raw_y, target_y, video_name):
    """
    입력과 정답의 높이 분포를 시각화합니다.
    
    Args:
        raw_y: 원본 Y 좌표 (T, 33)
        target_y: 보정된 Y 좌표 (T, 33)
        video_name: 비디오 이름
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Height Distribution Analysis', fontsize=16, fontweight='bold')
    
    # 1. Overall height histogram
    axes[0, 0].hist(raw_y.flatten(), bins=100, alpha=0.7, label='Input (Raw)', color='red')
    axes[0, 0].hist(target_y.flatten(), bins=100, alpha=0.7, label='Target (Corrected)', color='blue')
    axes[0, 0].set_xlabel('Height (Y coordinate)')
    axes[0, 0].set_ylabel('Frequency')
    axes[0, 0].set_title('Overall Keypoint Height Distribution')
    axes[0, 0].legend()
    axes[0, 0].grid(alpha=0.3)
    
    # 2. 발 높이 시계열
    LEFT_FOOT = 31
    RIGHT_FOOT = 32
    frames = np.arange(len(raw_y))
    
    axes[0, 1].plot(frames, raw_y[:, LEFT_FOOT], label='Input - Left foot', color='red', alpha=0.6)
    axes[0, 1].plot(frames, raw_y[:, RIGHT_FOOT], label='Input - Right foot', color='orange', alpha=0.6)
    axes[0, 1].plot(frames, target_y[:, LEFT_FOOT], label='Target - Left foot', color='blue', linewidth=2)
    axes[0, 1].plot(frames, target_y[:, RIGHT_FOOT], label='Target - Right foot', color='cyan', linewidth=2)
    axes[0, 1].axhline(y=0, color='black', linestyle='--', label='Ground (y=0)')
    axes[0, 1].set_xlabel('Frame')
    axes[0, 1].set_ylabel('Height (Y coordinate)')
    axes[0, 1].set_title('Foot Height Time Series Comparison')
    axes[0, 1].legend()
    axes[0, 1].grid(alpha=0.3)
    
    # 3. 박스 플롯
    axes[1, 0].boxplot([raw_y.flatten(), target_y.flatten()], 
                       labels=['Input (Raw)', 'Target (Corrected)'])
    axes[1, 0].set_ylabel('Height (Y coordinate)')
    axes[1, 0].set_title('Height Distribution Box Plot')
    axes[1, 0].grid(alpha=0.3)
    
    # 4. 음수 높이 비율 비교
    raw_negative = np.sum(raw_y < 0) / raw_y.size * 100
    target_negative = np.sum(target_y < 0) / target_y.size * 100
    
    axes[1, 1].bar(['Input (Raw)', 'Target (Corrected)'], 
                   [raw_negative, target_negative],
                   color=['red', 'blue'])
    axes[1, 1].set_ylabel('Negative Height Ratio (%)')
    axes[1, 1].set_title('Ground Penetration Issue Improvement')
    axes[1, 1].grid(alpha=0.3)
    
    # 값 표시
    for i, v in enumerate([raw_negative, target_negative]):
        axes[1, 1].text(i, v + 1, f'{v:.2f}%', ha='center', va='bottom', fontweight='bold')
    
    plt.tight_layout()
    
    # 저장
    output_path = os.path.join(OUTPUT_DIR, f"{video_name}_height_analysis.png")
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"    Visualization saved: {output_path}")
    
    plt.close()


def visualize_keypoint_positions():
    """
    대표 프레임에서 키포인트 위치를 3D로 시각화합니다.
    """
    raw_files = sorted(glob(f"{PROCESSED_DIR}/*_raw.npy"))
    
    print("\n" + "=" * 80)
    print("Keypoint 3D Visualization")
    print("=" * 80)
    
    for raw_path in raw_files[:1]:  # First video only
        target_path = raw_path.replace("_raw.npy", "_target.npy")
        video_name = os.path.basename(raw_path).replace("_raw.npy", "")
        
        raw_data = np.load(raw_path)
        target_data = np.load(target_path)
        
        # Select middle frame
        mid_frame = len(raw_data) // 2
        
        fig = plt.figure(figsize=(16, 7))
        
        # Input data (raw)
        ax1 = fig.add_subplot(121, projection='3d')
        raw_frame = raw_data[mid_frame]  # (33, 3)
        ax1.scatter(raw_frame[:, 0], raw_frame[:, 2], raw_frame[:, 1], 
                   c='red', s=50, alpha=0.8)
        ax1.set_xlabel('X')
        ax1.set_ylabel('Z')
        ax1.set_zlabel('Y (Height)')
        ax1.set_title(f'Input (Raw BlazePose) - Frame {mid_frame}')
        
        # Ground plane
        xlim = ax1.get_xlim()
        zlim = ax1.get_ylim()
        xx, zz = np.meshgrid(xlim, zlim)
        yy = np.zeros_like(xx)
        ax1.plot_surface(xx, zz, yy, alpha=0.2, color='gray')
        
        # Target data (corrected)
        ax2 = fig.add_subplot(122, projection='3d')
        target_frame = target_data[mid_frame]  # (33, 3)
        ax2.scatter(target_frame[:, 0], target_frame[:, 2], target_frame[:, 1], 
                   c='blue', s=50, alpha=0.8)
        ax2.set_xlabel('X')
        ax2.set_ylabel('Z')
        ax2.set_zlabel('Y (Height)')
        ax2.set_title(f'Target (Height Corrected) - Frame {mid_frame}')
        
        # Ground plane
        xlim = ax2.get_xlim()
        zlim = ax2.get_ylim()
        xx, zz = np.meshgrid(xlim, zlim)
        yy = np.zeros_like(xx)
        ax2.plot_surface(xx, zz, yy, alpha=0.2, color='gray')
        
        plt.tight_layout()
        
        output_path = os.path.join(OUTPUT_DIR, f"{video_name}_3d_visualization.png")
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"\n3D visualization saved: {output_path}")
        
        plt.close()


def main():
    """Main analysis pipeline"""
    print("\n" + "=" * 80)
    print("Training Data Analysis Script")
    print("=" * 80)
    
    # 1. Dataset statistics
    stats = analyze_dataset()
    
    # 2. Height correction effect analysis
    analyze_height_correction()
    
    # 3. 3D visualization
    visualize_keypoint_positions()
    
    print("\n" + "=" * 80)
    print("Analysis Complete!")
    print(f"Results saved to: {OUTPUT_DIR}")
    print("=" * 80)


if __name__ == "__main__":
    main()
