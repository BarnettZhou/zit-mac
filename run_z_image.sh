#!/bin/bash
#
# Z-Image Turbo GGUF 文生图运行脚本
# 适用于 Apple Silicon Mac (M3 Pro)
# 使用 stable-diffusion.cpp with Metal 加速
#

set -e

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 模型路径
DIT_MODEL="${SCRIPT_DIR}/models/z-image-turbo-Q8_0.gguf"
TE_MODEL="${SCRIPT_DIR}/models/Qwen3-4B-Q4_K_M.gguf"
VAE_MODEL="${SCRIPT_DIR}/models/ae.safetensors"

# stable-diffusion.cpp 可执行文件路径
SD_CLI="${SCRIPT_DIR}/stable-diffusion.cpp/build/bin/sd-cli"

# 默认参数
PROMPT=""
OUTPUT_DIR="${SCRIPT_DIR}/output"
PREFIX=""
WIDTH=512
HEIGHT=512
STEPS=4
SEED=-1
SAMPLING_METHOD="res_multistep"
SCHEDULER=""
GUIDANCE=3.5

# 获取当前日期
CURRENT_DATE=$(date +%Y-%m-%d)

# 处理 prefix，替换 %date% 并确保目录存在
process_prefix() {
    local prefix="$1"
    
    # 替换 %date% 为当前日期
    prefix="${prefix//%date%/$CURRENT_DATE}"
    
    # 提取目录部分和文件名前缀
    local dir_part=""
    local file_prefix=""
    
    if [[ "$prefix" == */* ]]; then
        # 包含目录分隔符
        dir_part="${prefix%/*}"
        file_prefix="${prefix##*/}"
    else
        # 没有目录，只有文件名前缀
        file_prefix="$prefix"
    fi
    
    # 构建完整输出目录
    local full_output_dir="$OUTPUT_DIR"
    if [[ -n "$dir_part" ]]; then
        full_output_dir="${OUTPUT_DIR}/${dir_part}"
    fi
    
    # 创建目录
    mkdir -p "$full_output_dir"
    
    # 查找下一个可用的编号
    local next_num=1
    while [[ -f "${full_output_dir}/${file_prefix}_$(printf "%04d" $next_num).png" ]]; do
        ((next_num++))
    done
    
    # 构建完整输出路径（使用 printf 格式）
    local output_file="${full_output_dir}/${file_prefix}_$(printf "%04d" $next_num).png"
    
    echo "$output_file"
}

# 显示帮助信息
show_help() {
    cat << EOF
Z-Image Turbo GGUF 文生图工具

用法: $0 [选项]

基本选项:
    -p, --prompt <text>     文本提示词 (必需)
    --prefix <prefix>       输出文件前缀 (默认: 空, 直接使用 output/目录)
                            支持 %date% 占位符, 会被替换为当前日期
                            例如: "aa/" 或 "%date%/aa"
                            最终文件名: {prefix}_0001.png (自动递增)
    -W, --width <num>       图像宽度 (默认: 512)
    -H, --height <num>      图像高度 (默认: 512)
    -s, --steps <num>       推理步数 (默认: 4, Turbo推荐4-8)
    --seed <num>            随机种子 (默认: 随机)

采样选项:
    --sampling-method <name>   采样方法 (默认: res_multistep)
                               可选: euler, euler_a, heun, dpm2, dpm++2s_a, dpm++2m,
                                     dpm++2mv2, ipndm, ipndm_v, lcm, ddim_trailing,
                                     tcd, res_multistep, res_2s
    --scheduler <name>         调度器 (默认: simple)
                               可选: discrete, karras, exponential, ays, gits, 
                                     smoothstep, sgm_uniform, simple, kl_optimal, lcm, bong_tangent
    --guidance <float>         蒸馏引导尺度 (默认: 3.5, 建议范围: 2.5-5.0)
                               越高: 提示词遵循越强, 越低: 更自然的质感

其他选项:
    -h, --help              显示此帮助信息

示例:
    # 基础用法 (保存到 output/output_0001.png)
    $0 -p "a beautiful sunset over mountains"

    # 使用前缀 (保存到 output/cat_0001.png)
    $0 -p "cute cat" --prefix "cat"

    # 使用子目录 (保存到 output/aa/cat_0001.png)
    $0 -p "cute cat" --prefix "aa/cat"

    # 使用日期子目录 (保存到 output/2026-03-29/cat_0001.png)
    $0 -p "cute cat" --prefix "%date%/cat"

    # 使用 euler + sgm_uniform 组合
    $0 -p "portrait" --prefix "%date%/portrait" --sampling-method euler --scheduler sgm_uniform

    # 高分辨率 + 更多步数
    $0 -p "landscape" --prefix "%date%/landscape" -W 1024 -H 1024 -s 8 --seed 42

注意:
    首次运行前需要手动下载依赖模型:
      文本编码器: https://huggingface.co/unsloth/Qwen3-4B-GGUF
      VAE: https://huggingface.co/Comfy-Org/z_image_turbo/tree/main/split_files/vae

EOF
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--prompt)
            PROMPT="$2"
            shift 2
            ;;
        --prefix)
            PREFIX="$2"
            shift 2
            ;;
        -W|--width)
            WIDTH="$2"
            shift 2
            ;;
        -H|--height)
            HEIGHT="$2"
            shift 2
            ;;
        -s|--steps)
            STEPS="$2"
            shift 2
            ;;
        --seed)
            SEED="$2"
            shift 2
            ;;
        --sampling-method)
            SAMPLING_METHOD="$2"
            shift 2
            ;;
        --scheduler)
            SCHEDULER="$2"
            shift 2
            ;;
        --guidance)
            GUIDANCE="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "错误: 未知选项 $1"
            show_help
            exit 1
            ;;
    esac
done

# 检查必需参数
if [[ -z "$PROMPT" ]]; then
    echo "错误: 必须提供提示词 (-p)"
    show_help
    exit 1
fi

# 检查模型文件是否存在
check_model() {
    local model_path="$1"
    local model_name="$2"
    if [[ ! -f "$model_path" ]]; then
        echo "错误: 缺少模型文件: $model_name"
        echo "路径: $model_path"
        echo ""
        echo "请手动下载模型文件:"
        echo "  文本编码器: https://huggingface.co/unsloth/Qwen3-4B-GGUF"
        echo "  VAE: https://huggingface.co/Comfy-Org/z_image_turbo/tree/main/split_files/vae"
        exit 1
    fi
}

echo "======================================"
echo "Z-Image Turbo 文生图"
echo "======================================"
echo ""

check_model "$DIT_MODEL" "DiT 模型 (z-image-turbo-Q8_0.gguf)"
check_model "$TE_MODEL" "文本编码器 (Qwen3-4B-Q4_K_M.gguf)"
check_model "$VAE_MODEL" "VAE (ae.safetensors)"

# 检查可执行文件
if [[ ! -f "$SD_CLI" ]]; then
    echo "错误: 找不到 sd-cli 可执行文件"
    echo "路径: $SD_CLI"
    echo ""
    echo "请先编译 stable-diffusion.cpp:"
    echo "  cd stable-diffusion.cpp"
    echo "  cmake -B build -DSD_METAL=ON"
    echo "  cmake --build build -j8"
    exit 1
fi

# 确定输出文件路径
if [[ -n "$PREFIX" ]]; then
    OUTPUT=$(process_prefix "$PREFIX")
else
    # 默认使用 output 作为前缀
    OUTPUT=$(process_prefix "output")
fi

echo "生成参数:"
echo "  提示词: $PROMPT"
echo "  尺寸: ${WIDTH}x${HEIGHT}"
echo "  步数: $STEPS"
echo "  种子: $SEED"
echo "  采样方法: $SAMPLING_METHOD"
if [[ -n "$SCHEDULER" ]]; then
    echo "  调度器: $SCHEDULER"
fi
echo "  Guidance: $GUIDANCE"
echo "  输出: $OUTPUT"
echo ""
echo "模型信息:"
echo "  DiT: $DIT_MODEL"
echo "  TE:  $TE_MODEL"
echo "  VAE: $VAE_MODEL"
echo ""
echo "正在生成..."
echo "======================================"

# 构建命令
CMD=("$SD_CLI"
    -M img_gen
    --diffusion-model "$DIT_MODEL"
    --llm "$TE_MODEL"
    --vae "$VAE_MODEL"
    -p "$PROMPT"
    --width "$WIDTH"
    --height "$HEIGHT"
    --steps "$STEPS"
    --seed "$SEED"
    -o "$OUTPUT"
    --sampling-method "$SAMPLING_METHOD"
    --cfg-scale 1.0
    --guidance "$GUIDANCE"
    -v
)

# 如果指定了调度器，添加参数
if [[ -n "$SCHEDULER" ]]; then
    CMD+=(--scheduler "$SCHEDULER")
fi

# 运行生成
"${CMD[@]}"

echo ""
echo "======================================"
echo "生成完成!"
echo "输出文件: $OUTPUT"
echo "======================================"
