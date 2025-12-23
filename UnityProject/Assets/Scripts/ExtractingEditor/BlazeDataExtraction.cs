using System;
using System.Collections;
using System.Collections.Generic;
//using System.Diagnostics;
using System.IO;
using System.Text;
using Unity.VisualScripting;
using UnityEditor;
using UnityEditor.Experimental.GraphView;
using UnityEditorInternal;
using UnityEngine;
using UnityEngine.TextCore.Text;
//using System.Diagnostics;

public class BlazeDataExtraction : RealTimeAnimation
{
    public bool b_play = false;
    public int StartFrame = 1;
    public BlazePoseDataFile _BlazeMotionData;
    public Actor Character;

    // ▼ [추가됨] 음악 플레이어를 연결할 변수입니다.
    [Header("Audio Settings")]
    public AudioSource bgmPlayer;

    // ▼ [카메라 설정] - 메인, 왼쪽, 오른쪽 카메라
    [Header("Camera Settings")]
    public Camera mainCamera;
    public Camera leftCamera;
    public Camera rightCamera;

    // ▼ [자동 시점 변환 설정]
    [Tooltip("몇 초마다 카메라를 자동으로 바꿀지 설정합니다.")]
    public float autoSwitchInterval = 5.0f; // 기본 5초
    private float cameraTimer = 0f;

    // 현재 보고 있는 카메라 번호 (0:메인, 1:왼쪽, 2:오른쪽)
    public int currentCameraIndex = 0;

    // joint root cubes
    public Transform jointRoot;
    public float cube_scale = 0.02f;
    public float human_size_scale = 5f;
    public float bone_size = 0.12f;

    public GameObject capsulePrefab;     // 기본 캡슐 프리팹
    [SerializeField] 
    public List<GameObject> capsules = new List<GameObject>();
    public float capsuleRadius = 0.15f;


    private List<GameObject> jointCubes = new List<GameObject>();
    public BlazePoseSkeletonBuilder skel_build_bp;

    // 회전 리타게팅용 캐시
    private Dictionary<int, Quaternion> boneRestRotations = new Dictionary<int, Quaternion>();
    private Dictionary<int, Vector3> boneRestDir = new Dictionary<int, Vector3>(); // 본이 바라보는 기본 방향
    private bool restPoseCaptured = false;

    // Blaze index별로 "어느 자식을 보고 방향을 잡을지" 정의
    // (부모 Blaze → 자식 Blaze)
    private static readonly Dictionary<int, int> directionChildMap = new Dictionary<int, int>
    {
        {11, 13}, // LeftUpperArm  -> LeftElbow
        {13, 15}, // LeftLowerArm  -> LeftWrist
        {12, 14}, // RightUpperArm -> RightElbow
        {14, 16}, // RightLowerArm -> RightWrist
        {23, 25}, // LeftUpperLeg  -> LeftKnee
        {25, 27}, // LeftLowerLeg  -> LeftAnkle
        {24, 26}, // RightUpperLeg -> RightKnee
        {26, 28}, // RightLowerLeg -> RightAnkle
        {27, 31}, // LeftFoot -> LeftToes
        {28, 32}, // RightFoot -> RightToes
    };

    // ▼ [수정됨] Update -> LateUpdate로 변경하여 부모 클래스와 충돌 방지
    public void LateUpdate()
    {
        if (b_play)
        {
            /* 1. 애니메이션 데이터 읽기
            _BlazeMotionData.ReadData(Frame);
            UpdateJointCubes();

            if (Character != null)
            {
                skel_build_bp.UpdateSkeleton(Character, _BlazeMotionData, human_size_scale);
            }

            // 2. 프레임 진행
            Frame += 1;
            if (Frame >= _BlazeMotionData.GetTotalFrames())
            {
                Frame = StartFrame;
            }
            */
            // ▼ [자동 카메라 전환 로직]
            // 시간이 흐르게 함
            cameraTimer += Time.deltaTime;

            // 설정한 시간(autoSwitchInterval)이 지나면 다음 카메라로 전환
            if (cameraTimer >= autoSwitchInterval)
            {
                cameraTimer = 0f; // 타이머 초기화
                SwitchNextCamera(); // 카메라 전환 함수 호출
            }
            
        }
    }

    // --------------------------------------------------------------------------------
    //  카메라 전환 함수 (0 -> 1 -> 2 -> 0 반복)
    // --------------------------------------------------------------------------------
    public void SwitchNextCamera()
    {
        currentCameraIndex = (currentCameraIndex + 1) % 3;
        UpdateCameraActiveState();
    }

    // 카메라 활성/비활성 상태 적용
    public void UpdateCameraActiveState()
    {
        if (mainCamera != null) mainCamera.gameObject.SetActive(currentCameraIndex == 0);
        if (leftCamera != null) leftCamera.gameObject.SetActive(currentCameraIndex == 1);
        if (rightCamera != null) rightCamera.gameObject.SetActive(currentCameraIndex == 2);
    }

    // --------------------------------------------------------------------------------
    //  초기화 / 큐브 생성
    // --------------------------------------------------------------------------------
    public void CreateJointCubes()
    {
        foreach (var c in jointCubes)
        {
            if (c != null) DestroyImmediate(c);
        }
        jointCubes.Clear();

        for (int i = 0; i < 33; i++)
        {
            GameObject cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
            cube.name = "Joint_" + i;
            cube.transform.SetParent(jointRoot != null ? jointRoot : this.transform);
            cube.transform.localScale = Vector3.one * cube_scale;
            cube.SetActive(false);
            jointCubes.Add(cube);
        }
    }

    private void UpdateJointCubes()
    {
        if (jointCubes.Count < 33) return;
        /*
        for (int i = 0; i < 33; i++)
        {
            Vector3 pos = _BlazeMotionData.GetJointPosition(i);
            jointCubes[i].SetActive(true);
            jointCubes[i].transform.localPosition = pos * human_size_scale;
        }
        */
    }

    protected override void Setup()
    {
        _BlazeMotionData = ScriptableObject.CreateInstance<BlazePoseDataFile>();
        b_play = false;
        cube_scale = 0.02f;
    }
    protected override void Close()
    {

    }
    
    //feed functions
    Vector3 ConvertBlazeToUnity(Vector3 bp)
    {
        // y축 반전, z축 방향 전환 (필요 시)
        return new Vector3(-bp.x, bp.y, -bp.z);
    }
    public void UpdateCubes(Transform jointRoot, Vector3[] currentPose)
    {
        if (jointRoot == null)
        {
            Debug.LogWarning(" joint_root is null. Please assign it first.");
            return;
        }

        if (currentPose == null || currentPose.Length == 0)
        {
            Debug.LogWarning("currentPose is empty.");
            return;
        }

        // joint_root 아래의 자식들 중 joint_i 이름을 가진 오브젝트를 찾아 업데이트
        for (int i = 0; i < currentPose.Length; i++)
        {
            Transform joint = jointRoot.Find($"joint_{i}");
            if (joint != null)
            {
                Vector3 position_blaze_to_unity = ConvertBlazeToUnity(currentPose[i])*human_size_scale;
                joint.localPosition = position_blaze_to_unity;
                joint.transform.localScale = new Vector3(capsuleRadius, capsuleRadius, capsuleRadius);
            
            }
            else
            {
                Debug.LogWarning($"⚠️ joint_{i} not found under {jointRoot.name}");
            }
        }
    }
    public Quaternion ComputeRotation(Vector3[] worldJointPos)
    {
        // 1. compute forward
        Vector3 leftShoulder = worldJointPos[11];
        Vector3 rightShoulder = worldJointPos[12];
        Vector3 leftHip = worldJointPos[23];
        Vector3 rightHip = worldJointPos[24];
        // 1.1. right vector
        Vector3 right_axis = rightShoulder - leftShoulder;
        right_axis[1] = 0; // horizontal projection of shoulder vector
        right_axis = right_axis.normalized;
        // 1.2. up vector
        Vector3 shoulder_center = (leftShoulder + rightShoulder)/2;
        Vector3 hip_center      = (leftHip + rightHip)/2;
        Vector3 up = (shoulder_center - hip_center).normalized;
        // 1.3. compute forward & orthogonalized up axis
        Vector3 forward_axis = Vector3.Cross(right_axis,up).normalized;
        Vector3 up_axis = Vector3.Cross(forward_axis,right_axis).normalized;

        // 2. compute rotation
        Matrix4x4 rotMatrix = Matrix4x4.identity;
        rotMatrix.SetColumn(0, new Vector4(right_axis.x, right_axis.y, right_axis.z, 0f));     // X axis
        rotMatrix.SetColumn(1, new Vector4(up_axis.x,    up_axis.y,    up_axis.z,    0f));     // Y axis
        rotMatrix.SetColumn(2, new Vector4(forward_axis.x, forward_axis.y, forward_axis.z, 0f)); // Z axis
        rotMatrix.SetColumn(3, new Vector4(0,0,0,1));
        
        return rotMatrix.rotation;
    }
    Vector3 ToPelvisLocal(Vector3 worldJoint, Quaternion pelvisRot, Vector3 pelvisPos)
    {
        // 1) translation 제거
        Vector3 p = worldJoint - pelvisPos;

        // 2) rotation 역변환 적용
        //   world → local 이므로 inverse 회전 적용
        return Quaternion.Inverse(pelvisRot) * p;
    }

    public void ComputeLocalPositions(Vector3[] worldJointPos, out Matrix4x4 origin, out Vector3[] localJointPos)
    {
        int hipL = 23;
        int hipR = 24;
        // pelvis position
        Vector3 hipPos = (worldJointPos[hipL] + worldJointPos[hipR]) * 0.5f;
        // pelvis rotation
        Quaternion hipRot = ComputeRotation(worldJointPos);
        // pelvis world origin
        Matrix4x4 pelvis = Matrix4x4.identity; 
        pelvis.SetTRS(hipPos,hipRot,pelvis.GetScale());
        origin = pelvis;
        // compute local positions
        Vector3[] _localJntPos = new Vector3[worldJointPos.Length];
        for (int i=0; i <worldJointPos.Length; i++)
        {
            _localJntPos[i] = ToPelvisLocal(worldJointPos[i],hipRot,hipPos);
        }
        localJointPos = _localJntPos;

    }
    public void UpdateBlazePose(BlazePoseSkeletonBuilder skel_bp, Vector3[] currentPose)
    {
        if (currentPose == null || currentPose.Length == 0) return;
        if (skel_bp == null || skel_bp.boneMap == null || skel_bp.boneMap.Count == 0) return;
        if (Character == null || Character.Bones == null) return;

        // 첫 프레임에 아직 캡처 안 했으면 T-pose 기준 정보 저장
        if (!restPoseCaptured)
        {
            CaptureRestPose(skel_bp);
        }

        // 1) BlazePose 좌표를 Unity 좌표로 모두 변환
        Vector3[] worldJointPos = new Vector3[currentPose.Length];
        for (int i = 0; i < currentPose.Length; i++)
        {
            worldJointPos[i] = ConvertBlazeToUnity(currentPose[i]) * human_size_scale;
        }

        // 2) compute pelvis origin
        Matrix4x4 pelvis = Matrix4x4.identity;
        Vector3[] local_positions = new Vector3[currentPose.Length];
        ComputeLocalPositions(worldJointPos,out pelvis,out local_positions);
        Character.Bones[2].Transform.SetPositionAndRotation(pelvis.GetPosition(),pelvis.rotation);

        // 3) 각 본의 회전을 방향 벡터 기반으로 갱신
        foreach (var kv in skel_bp.boneMap)
        {
            int parentBlaze = kv.Key;
            int parentBone = kv.Value;

            int childBlaze;
            if (!directionChildMap.TryGetValue(parentBlaze, out childBlaze))
                continue;

            if (parentBlaze < 0 || parentBlaze >= worldJointPos.Length) continue;
            if (childBlaze < 0 || childBlaze >= worldJointPos.Length) continue;

            if (!boneRestRotations.ContainsKey(parentBone) ||
                !boneRestDir.ContainsKey(parentBone))
                continue;

            // BlazePose 기준 현재 방향 (부모 -> 자식)
            Vector3 targetDir = worldJointPos[childBlaze] - worldJointPos[parentBlaze];
            if (targetDir.sqrMagnitude < 1e-6f) continue;
            targetDir.Normalize();

            // 캐릭터 기본 포즈에서의 방향 / 회전
            Vector3 restDir = boneRestDir[parentBone];
            Quaternion restRot = boneRestRotations[parentBone];

            // 기본 방향 -> 현재 방향으로 회전 델타 계산
            Quaternion delta = Quaternion.FromToRotation(pelvis.rotation * restDir, targetDir);
            
            // 최종 회전 = 델타 * 기본 회전
            Character.Bones[parentBone].Transform.rotation = delta * pelvis.rotation * restRot;
        }
    }


    public void DrawBlazeSkel(BlazePoseSkeletonBuilder skel_bp, float boneSize, Color boneColor)
    {
        // 1. boneMap이 없거나 비어있으면 바로 리턴
        if (skel_bp == null || skel_bp.boneMap == null || skel_bp.boneMap.Count == 0)
        {
            Debug.LogWarning("[DrawBlazeSkel] boneMap is not initialized — skipping draw.");
            return;
        }

        // 2. blazePoseBones도 체크
        if (skel_bp.blazePoseBones == null || skel_bp.blazePoseBones.GetLength(0) == 0)
        {
            Debug.LogWarning("[DrawBlazeSkel] blazePoseBones is not defined — skipping draw.");
            return;
        }

        UltiDraw.Begin();

        for (int i = 0; i < skel_bp.blazePoseBones.GetLength(0); i++)
        {
            int parent = skel_bp.blazePoseBones[i, 0];
            int child = skel_bp.blazePoseBones[i, 1];

            int map_parent = skel_bp.boneMap[parent];
            int map_child = skel_bp.boneMap[child];

            if (parent < 0 || parent >= Character.Bones.Length) continue;
            if (child < 0 || child >= Character.Bones.Length) continue;
            if (Character.Bones[map_parent] == null || Character.Bones[map_child] == null) continue;

            Vector3 parentPos = Character.Bones[map_parent].Transform.position;
            Vector3 childPos = Character.Bones[map_child].Transform.position;

            float length = Vector3.Distance(parentPos, childPos);

            //UltiDraw.DrawLine(parentPos, childPos,boneSize, boneColor);

            UltiDraw.DrawBone(
                parentPos,
                Quaternion.FromToRotation(Vector3.forward, (childPos - parentPos).normalized),
                12.5f * boneSize * length,
                length,
                Color.grey
            ); // boneColor.Transparent(1f)
        }

        UltiDraw.End();
    }
    
    // Capsule visualization
    public void BuildCapsules(BlazePoseSkeletonBuilder skel_bp)
    {
        // 이전 캡슐 제거
        foreach (var cap in capsules)
            DestroyImmediate(cap);
        capsules.Clear();

        if (capsulePrefab == null)
        {
            capsulePrefab = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            capsulePrefab.name = "CapsulePrefab";
            capsulePrefab.SetActive(true); // 템플릿용
        }

        GameObject capsuleRoot = new GameObject("Capsules");
        // 캡슐 생성
        for (int i = 0; i < skel_bp.blazePoseBones.GetLength(0); i++)
        {
            GameObject capsule = Instantiate(capsulePrefab, capsuleRoot.transform);
            capsule.name = $"Capsule_{i}";
            capsule.transform.localScale = new Vector3(capsuleRadius, 0.05f, capsuleRadius);
            capsules.Add(capsule);
        }
    }

    public void EnsureCapsulesExist(BlazePoseSkeletonBuilder skel_bp)
    {
        if (capsules == null)
            capsules = new List<GameObject>();

        // 리스트 길이, null 요소까지 모두 체크해서 이상하면 재빌드
        bool needRebuild = false;

        int expectedCount = skel_bp.blazePoseBones.GetLength(0);

        if (capsules.Count != expectedCount)
        {
            needRebuild = true;
        }
        else
        {
            for (int i = 0; i < capsules.Count; i++)
            {
                if (capsules[i] == null)
                {
                    needRebuild = true;
                    break;
                }
            }
        }

        if (needRebuild)
        {
            Debug.Log("Capsules are missing or invalid — rebuilding.");
            BuildCapsules(skel_build_bp);
        }
        else
        {
            Debug.Log("Using existing capsules from Inspector.");
        }
    }


    public void UpdateCapsules(BlazePoseSkeletonBuilder skel_bp, Actor actor)
    {
        // 안전장치
        if (skel_bp == null || skel_bp.boneMap == null) return;
        if (capsules == null || capsules.Count == 0) return;

        for (int i = 0; i < skel_bp.blazePoseBones.GetLength(0); i++)
        {
            int parent = skel_bp.blazePoseBones[i, 0];
            int child = skel_bp.blazePoseBones[i, 1];

            // boneMap에 인덱스가 없으면 그냥 스킵
            if (!skel_bp.boneMap.ContainsKey(parent) ||
                !skel_bp.boneMap.ContainsKey(child))
            {
                continue;
            }

            int map_parent = skel_bp.boneMap[parent];
            int map_child = skel_bp.boneMap[child];

            if (parent < 0 || parent >= actor.Bones.Length) continue;
            if (child < 0 || child >= actor.Bones.Length) continue;
            if (actor.Bones[map_parent] == null || actor.Bones[map_child] == null) continue;

            // 캡슐 null 체크 방어코드
            if (i >= capsules.Count || capsules[i] == null) continue;

            Vector3 parentPos = actor.Bones[map_parent].Transform.position;
            Vector3 childPos = actor.Bones[map_child].Transform.position;

            bool isHand = false;
            UpdateCapsuleTransform(capsules[i], parentPos, childPos, isHand);
        }
    }


    // ============================
    // ③ 캡슐 위치/회전 업데이트
    // ============================
    private void UpdateCapsuleTransform(GameObject capsule, Vector3 start, Vector3 end, bool isHand)
    {
        Vector3 offset = end - start;
        Vector3 position = start + offset / 2.0f;
        capsule.transform.position = position;
        capsule.transform.rotation = Quaternion.FromToRotation(Vector3.up, offset);

        float length = offset.magnitude;
        capsule.transform.localScale = new Vector3(capsuleRadius, length / 2.0f + 0.03f, capsuleRadius);

        if (isHand && capsule.transform.childCount > 0)
        {
            Transform hand = capsule.transform.GetChild(0);
            if (hand != null)
            {
                hand.localScale = new Vector3(capsuleRadius, 1.0f, capsuleRadius);
                hand.localRotation = Quaternion.FromToRotation(Vector3.up, offset);
                hand.position = end;
            }
        }
    }

    /// <summary>
    /// 캐릭터 T-pose 상태에서
    /// - 각 본의 기본 회전
    /// - 각 본이 바라보는 기본 방향(부모→자식)
    /// 을 한 번만 저장
    /// </summary>
    public void CaptureRestPose(BlazePoseSkeletonBuilder skel_bp)
    {
        boneRestRotations.Clear();
        boneRestDir.Clear();
        restPoseCaptured = false;

        if (Character == null || Character.Bones == null)
        {
            Debug.LogWarning("[BlazeDataExtraction] Character is null, cannot capture rest pose.");
            return;
        }

        if (skel_bp == null || skel_bp.boneMap == null || skel_bp.boneMap.Count == 0)
        {
            Debug.LogWarning("[BlazeDataExtraction] skel_bp / boneMap not ready.");
            return;
        }

        // 1) 각 본의 월드 기준 기본 회전 저장
        foreach (var kv in skel_bp.boneMap)
        {
            int boneIndex = kv.Value;
            if (boneIndex < 0 || boneIndex >= Character.Bones.Length) continue;

            Transform t = Character.Bones[boneIndex].Transform;
            boneRestRotations[boneIndex] = t.rotation;
        }

        // 2) 각 본이 바라보는 방향 저장
        foreach (var kv in skel_bp.boneMap)
        {
            int parentBlaze = kv.Key;
            int parentBone = kv.Value;

            int childBlaze;
            if (!directionChildMap.TryGetValue(parentBlaze, out childBlaze))
                continue; // Blaze joint는 방향을 정의X

            if (!skel_bp.boneMap.ContainsKey(childBlaze))
                continue; // 자식 Blaze가 매핑돼 있지 않으면 스킵

            int childBone = skel_bp.boneMap[childBlaze];

            Transform tParent = Character.Bones[parentBone].Transform;
            Transform tChild = Character.Bones[childBone].Transform;

            Vector3 dir = tChild.position - tParent.position;
            if (dir.sqrMagnitude < 1e-6f) continue;
            dir.Normalize();

            boneRestDir[parentBone] = dir;
        }


        restPoseCaptured = true;
        Debug.Log("[BlazeDataExtraction] Rest pose captured.");
    }


    protected override void Feed()
    {
        // Vector3 vector = _BlazeMotionData.frameDict[0][0];
        // Debug.Log("see " + vector);
        if (b_play)
        {

            // import single data from csvList;
            if (Frame == StartFrame)
            {
                _BlazeMotionData.ImportCSVData(_BlazeMotionData.selectedData, 1.0f);
                EnsureCapsulesExist(skel_build_bp);
            }

            // initialize the data
            if (Frame >= _BlazeMotionData.frameDict.Count)
            {
                b_play = false;
                return;
            }
            else
            {
                Vector3[] currentPose = _BlazeMotionData.frameDict[Frame].ToArray();

                //Debug.Log($" Frame : {Frame} , currentPose {currentPose[0]} / {currentPose.Length}");
                UpdateBlazePose(skel_build_bp, currentPose);
                
                Frame++;
            }
        }

    }
    protected override void Read()
    {
    }
    protected override void Postprocess()
    { }
    protected override void OnGUIDerived()
    { }
    protected override void OnRenderObjectDerived()
    {
        //DrawBlazeSkel(skel_build_bp, bone_size, Color.cyan);
    }

    
    [CustomEditor(typeof(BlazeDataExtraction), true)]
    public class BlazeDataExtraction_Editor : Editor
    {
        public BlazeDataExtraction Target;
        public void Awake()
        {
            Target = (BlazeDataExtraction)target;
            //Target.is_random = true;
            Target.skel_build_bp = ScriptableObject.CreateInstance<BlazePoseSkeletonBuilder>();
        }
        public override void OnInspectorGUI()
        {
            Inspector();
        }
        private void Inspector()
        {
            Utility.ResetGUIColor();
            Utility.SetGUIColor(UltiDraw.LightGrey);

            // Assigning Target Avatar
            EditorGUILayout.BeginVertical();
            Target.Character = (Actor)EditorGUILayout.ObjectField("Source Actor", Target.Character, typeof(Actor), true);
            EditorGUILayout.EndVertical();

            // ▼ [추가됨] Inspector에 AudioSource 연결 필드 표시
            Target.bgmPlayer = (AudioSource)EditorGUILayout.ObjectField("BGM Player", Target.bgmPlayer, typeof(AudioSource), true);

            if (Target._BlazeMotionData != null)
            {
                //BlazeData
                Target._BlazeMotionData.MotionCSVFile_Inspector(Target.Character);
            }

            Target.human_size_scale = EditorGUILayout.FloatField("human_scale", Target.human_size_scale);

            EditorGUILayout.Space(10);

            // ▼ [카메라 연결 필드]
            EditorGUILayout.LabelField("Camera Setup", EditorStyles.boldLabel);
            Target.mainCamera = (Camera)EditorGUILayout.ObjectField("Main Camera", Target.mainCamera, typeof(Camera), true);
            Target.leftCamera = (Camera)EditorGUILayout.ObjectField("Left Camera", Target.leftCamera, typeof(Camera), true);
            Target.rightCamera = (Camera)EditorGUILayout.ObjectField("Right Camera", Target.rightCamera, typeof(Camera), true);

            // play button
            if (Utility.GUIButton("reset & play animation", Color.white, Color.red))
            {
                if (Target.Character != null)
                {
                    Animator anim = Target.Character.GetComponentInChildren<Animator>();

                    if (anim != null && anim.isHuman)
                    {
                        // 휴머노이드 캐릭터라면 자동 Humanoid 매핑 사용
                        Target.skel_build_bp.BuildHumanoidMapping(Target.Character, anim);
                    }
                    else
                    {
                        // 아니면 기존 매핑 사용
                        Target.skel_build_bp.BuildMapping(Target.Character);
                    }
                }

                // ▼ [추가됨] 버튼 클릭 시 음악 리셋 및 재생 로직
                if (Target.bgmPlayer != null)
                {
                    Target.bgmPlayer.Stop(); // 재생 중이면 멈춤
                    Target.bgmPlayer.Play(); // 처음부터 다시 재생
                }
                else
                {
                    Debug.LogWarning("BGM Player가 연결되지 않았습니다. Inspector에서 AudioSource를 연결해주세요.");
                }

                // ▼ [추가됨] 카메라 초기화 (메인부터 시작)
                Target.currentCameraIndex = 0;
                Target.UpdateCameraActiveState();
                Target.cameraTimer = 0f; // 타이머도 0초로 리셋

                Target.Frame = Target.StartFrame;
                Target.b_play = true;
            }

        }

    }
}
