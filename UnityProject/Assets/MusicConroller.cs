using UnityEngine;

public class MusicController : MonoBehaviour
{
    public AudioSource audioSource; // 1단계에서 만든 오디오 소스를 여기에 연결할 거예요.

    // 버튼이 눌리면 실행될 함수
    public void OnResetAndPlayClicked()
    {
        // 1. 만약 음악이 나오고 있었다면 멈춤 (리셋 효과)
        audioSource.Stop();

        // 2. 음악을 처음부터 다시 재생
        audioSource.Play();

        Debug.Log("음악이 리셋되고 다시 재생됩니다!");
    }
}
