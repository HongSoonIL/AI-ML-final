import numpy as np
import matplotlib.pyplot as plt
import os

def calculate_angle(a, b, c):
    """
    세 점 a, b, c 사이의 각도를 계산 (b가 중심점)
    """
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)

    ba = a - b
    bc = c - b

    cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
    angle = np.arccos(np.clip(cosine_angle, -1.0, 1.0))

    return np.degrees(angle)

def analyze_and_plot(raw_data, refined_data, output_dir, filename_prefix="motion"):
    """
    Raw 데이터와 Refined 데이터의 모션(각도, 속도)을 비교 분석하여 그래프로 저장합니다.
    data shape: (T, 33, 3)
    """
    os.makedirs(output_dir, exist_ok=True)
    T = raw_data.shape[0]
    
    # 1. 무릎 각도 (왼쪽: 23-25-27)
    raw_angles = []
    refined_angles = []
    
    # 2. 손목 속도 (오른쪽 손목: 16)
    raw_velocities = []
    refined_velocities = []

    for t in range(T):
        # 각도 계산
        ra = calculate_angle(raw_data[t, 23], raw_data[t, 25], raw_data[t, 27])
        fa = calculate_angle(refined_data[t, 23], refined_data[t, 25], refined_data[t, 27])
        raw_angles.append(ra)
        refined_angles.append(fa)

        # 속도 계산 (t > 0)
        if t > 0:
            rv = np.linalg.norm(raw_data[t, 16] - raw_data[t-1, 16])
            fv = np.linalg.norm(refined_data[t, 16] - refined_data[t-1, 16])
            raw_velocities.append(rv)
            refined_velocities.append(fv)
        else:
            raw_velocities.append(0)
            refined_velocities.append(0)

    # --- 그래프 1: 무릎 각도 (Smoothness 확인) ---
    plt.figure(figsize=(12, 5))
    plt.plot(raw_angles, label='Raw Knee Angle', alpha=0.5, linestyle='--')
    plt.plot(refined_angles, label='Refined Knee Angle', linewidth=2)
    plt.title(f"Joint Angle Smoothing Analysis ({filename_prefix})")
    plt.xlabel("Frame")
    plt.ylabel("Angle (degrees)")
    plt.legend()
    plt.grid(True)
    plt.savefig(os.path.join(output_dir, f"{filename_prefix}_angle_analysis.png"))
    plt.close()

    # --- 그래프 2: 손목 속도 (Jitter/Noise 감소 확인) ---
    plt.figure(figsize=(12, 5))
    plt.plot(raw_velocities, label='Raw Wrist Velocity', alpha=0.5, color='red')
    plt.plot(refined_velocities, label='Refined Wrist Velocity', color='green')
    plt.title(f"Velocity/Jitter Reduction Analysis ({filename_prefix})")
    plt.xlabel("Frame")
    plt.ylabel("Velocity (m/frame)")
    plt.legend()
    plt.grid(True)
    plt.savefig(os.path.join(output_dir, f"{filename_prefix}_velocity_analysis.png"))
    plt.close()

    print(f"📊 모션 분석 그래프 저장 완료: {output_dir}")