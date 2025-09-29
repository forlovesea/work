import torch
import torchvision.transforms as transforms
from PIL import Image
from torchvision.models import vgg19
from torchvision.utils import save_image

import os

# 스타일 전송에 사용할 유틸 함수
def load_image(image_path, max_size=400, shape=None):
    image = Image.open(image_path).convert('RGB')

    if max(image.size) > max_size:
        size = max_size
    else:
        size = max(image.size)

    if shape is not None:
        size = shape  # 여기가 tuple (H, W) 이어야 함

    # 여기서 tuple이 아닌 경우 처리해주자
    if isinstance(size, int):
        resize = transforms.Resize((size, size))  # 정사각형
    else:
        resize = transforms.Resize(size)  # 이미 (H, W)

    in_transform = transforms.Compose([
        resize,
        transforms.ToTensor(),
        transforms.Normalize(
            (0.485, 0.456, 0.406),
            (0.229, 0.224, 0.225)
        )
    ])

    image = in_transform(image)[:3, :, :].unsqueeze(0)
    return image

# 이미지 저장 함수
def im_convert(tensor):
    image = tensor.to("cpu").clone().detach()
    image = image.numpy().squeeze()
    image = image.transpose(1, 2, 0)
    image = image * [0.229, 0.224, 0.225]
    image = image + [0.485, 0.456, 0.406]
    image = image.clip(0, 1)
    return image

# 스타일 전송 실행 함수
def apply_style(content_path, style_path, output_path='output.jpg'):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    content = load_image(content_path).to(device)
    #style = load_image(style_path, shape=content.shape[-2:]).to(device)
    shape = tuple(content.shape[-2:])  # torch.Size → (int, int)
    style = load_image(style_path, shape=shape).to(device)
    # VGG 모델 불러오기
    vgg = vgg19(pretrained=True).features.to(device).eval()

    # 학습된 스타일 전송 네트워크 사용 가능 (예: Fast Neural Style)
    # 여기선 간단히 하려 VGG 기반을 사용하지만,
    # 실사용에는 pre-trained 스타일 네트워크 추천

    # 🟟 더 고급 버전이 필요하면 `fast-neural-style`을 추천:
    # https://github.com/pytorch/examples/tree/main/fast_neural_style

    print("현재 이 코드는 스타일 특징 추출까지만 가능하며, 실제 스타일 매핑은 구현이 더 필요합니다.")
    # 참고: 완전한 스타일 전송 코드는 꽤 길어집니다.

# 예시 사용
apply_style(
    content_path='D:\my_pc_iplist.png',       # 변환할 사진
    style_path='D:\ghibli_style.jpg',       # 지브리 스타일 그림 (예: 하울, 이웃집 토토로 배경 등)
    output_path='D:\ghibli_output.jpg'
)
