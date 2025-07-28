from PIL import Image, ImageDraw, ImageFont, ImageChops


def pad_to_square(image: Image.Image,
                  fill_color=(0, 0, 0),
                  padding: int = 50) -> Image.Image:
    """
    先补成正方形，再在四周扩展padding像素。
    """
    width, height = image.size
    if width == height:
        square_img = image.copy()
    else:
        new_size = max(width, height)
        square_img = Image.new(image.mode, (new_size, new_size), fill_color)
        left = (new_size - width) // 2
        top = (new_size - height) // 2
        square_img.paste(image, (left, top))

    if padding > 0:
        final_size = square_img.size[0] + 2 * padding
        padded_img = Image.new(square_img.mode, (final_size, final_size),
                               fill_color)
        padded_img.paste(square_img, (padding, padding))
        return padded_img
    else:
        return square_img


def draw_axis(
        image: Image.Image,
        origin: tuple,
        img_size: tuple,
        grid_size: int = 50,
        show_numbers: bool = True,
        axis_color=(255, 255, 255),
        axis_width: int = 1,
        padding: int = 50,
        draw_lines: bool = True,
        draw_numbers: bool = True,
        number_mode: str = 'pixel'  # 'pixel' or 'grid'
) -> Image.Image:
    """
    在指定图像上绘制网格坐标轴和刻度数字。
    :param draw_lines: 是否绘制线条
    :param draw_numbers: 是否绘制数字
    :param number_mode: 'pixel' 显示像素数，'grid' 显示格数
    """
    img = image.copy()
    draw = ImageDraw.Draw(img)
    left, top = origin
    width, height = img_size
    left += padding
    top += padding

    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except IOError:
        font = ImageFont.load_default()

    # 横向网格线
    if draw_lines:
        for i in range(0, height + 1, grid_size):
            y = top + i
            draw.line([(left, y), (left + width, y)],
                      fill=axis_color,
                      width=axis_width)
    # 纵向网格线
    if draw_lines:
        for j in range(0, width + 1, grid_size):
            x = left + j
            draw.line([(x, top), (x, top + height)],
                      fill=axis_color,
                      width=axis_width)
    # 横向数字
    if draw_numbers:
        for i in range(0, height + 1, grid_size):
            if i > 0:
                y = top + i
                if number_mode == 'pixel':
                    label = str(i)
                else:
                    label = str(i // grid_size)
                draw.text((left - 35, y - 7), label, fill=axis_color, font=font)
    # 纵向数字
    if draw_numbers:
        for j in range(0, width + 1, grid_size):
            if j > 0:
                x = left + j
                if number_mode == 'pixel':
                    label = str(j)
                else:
                    label = str(j // grid_size)
                draw.text((x - 7, top - 35), label, fill=axis_color, font=font)
    # 原点处标注0
    if draw_numbers:
        draw.text((left - 35, top - 35), "0", fill=axis_color, font=font)
        # 横轴最大像素处标注图片宽度（仅当width不能被grid_size整除时）
        if width % grid_size != 0:
            draw.text((left + width - 20, top - 35),
                      str(width),
                      fill=axis_color,
                      font=font)
        # 纵轴最大像素处标注图片高度（仅当height不能被grid_size整除时）
        if height % grid_size != 0:
            draw.text((left - 35, top + height - 10),
                      str(height),
                      fill=axis_color,
                      font=font)
    return img


def prepare_grounding_image(image_path: str,
                            fill_color=(0, 0, 0),
                            axis_width=2,
                            grid_size=50,
                            show_numbers=True,
                            padding=50,
                            alpha=1.0,
                            number_mode: str = 'pixel') -> Image.Image:
    """
    综合处理流程：打开图片，补正方形，并使用遮罩方法添加反色坐标轴。
    :param image_path: 图片路径
    :param fill_color: 补边颜色
    :param axis_width: 坐标轴线宽
    :param grid_size: 网格间隔
    :param show_numbers: 是否显示刻度数字
    :param padding: 外扩像素数
    :param alpha: 反色坐标轴与原图融合的透明度（1.0为纯反色，0.5为半透明融合）
    :param number_mode: 'pixel' 显示像素数，'grid' 显示格数
    :return: 处理后的PIL图片
    """
    from PIL import ImageChops
    # 1. 打开并准备原图
    try:
        base_img = Image.open(image_path).convert('RGB')
    except FileNotFoundError:
        print(f"错误：找不到图片文件 {image_path}")
        return None

    original_size = base_img.size
    # 2. 将原图填充成带padding的正方形
    padded_img = pad_to_square(base_img, fill_color=fill_color, padding=padding)
    # 3. 创建一个原图的反色版本
    inverted_padded_img = ImageChops.invert(padded_img)
    # 4. 计算原图在正方形图中的左上角坐标
    width, height = original_size
    new_side = max(width, height)
    origin = ((new_side - width) // 2, (new_side - height) // 2)
    # 5. 生成线条mask和数字mask
    mask_line = Image.new('L', padded_img.size, 0)
    mask_number = Image.new('L', padded_img.size, 0)
    # 只画线
    axis_mask_line = draw_axis(mask_line,
                               origin,
                               original_size,
                               grid_size,
                               show_numbers,
                               255,
                               axis_width,
                               padding,
                               draw_lines=True,
                               draw_numbers=False,
                               number_mode=number_mode)
    # 只画数字
    axis_mask_number = draw_axis(mask_number,
                                 origin,
                                 original_size,
                                 grid_size,
                                 show_numbers,
                                 255,
                                 axis_width,
                                 padding,
                                 draw_lines=False,
                                 draw_numbers=True,
                                 number_mode=number_mode)
    # 6. 先用线条mask做半透明融合
    if alpha >= 1.0:
        temp_img = Image.composite(inverted_padded_img, padded_img,
                                   axis_mask_line)
    else:
        temp_img = apply_axis_mask_with_alpha(padded_img,
                                              axis_mask_line,
                                              alpha=alpha,
                                              axis_color=255)
    # 7. 再用数字mask做纯反色融合
    final_image = Image.composite(ImageChops.invert(temp_img), temp_img,
                                  axis_mask_number)
    return final_image


def apply_axis_mask_with_alpha(base_image: Image.Image,
                               axis_mask: Image.Image,
                               alpha: float = 0.5,
                               axis_color: int = 255) -> Image.Image:
    """
    将axis_mask中的坐标轴像素与base_image的反色进行半透明融合。
    :param base_image: 原始图片（已补正方形+padding）
    :param axis_mask: 只包含坐标轴线和数字的mask图（L模式，255为线）
    :param alpha: 反色融合的透明度（0~1）
    :param axis_color: mask中坐标轴线的像素值（默认255）
    :return: 融合后的新图片
    """
    from PIL import ImageChops
    base = base_image.convert('RGB')
    mask = axis_mask.convert('L')
    inverted = ImageChops.invert(base)
    out = base.copy()
    base_pixels = base.load()
    inverted_pixels = inverted.load()
    mask_pixels = mask.load()
    out_pixels = out.load()
    width, height = base.size
    for x in range(width):
        for y in range(height):
            if mask_pixels[x, y] == axis_color:
                r0, g0, b0 = base_pixels[x, y]
                r1, g1, b1 = inverted_pixels[x, y]
                r = int(r0 * (1 - alpha) + r1 * alpha)
                g = int(g0 * (1 - alpha) + g1 * alpha)
                b = int(b0 * (1 - alpha) + b1 * alpha)
                out_pixels[x, y] = (r, g, b)
            else:
                out_pixels[x, y] = base_pixels[x, y]
    return out
