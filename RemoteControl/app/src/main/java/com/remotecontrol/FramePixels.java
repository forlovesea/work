package com.remotecontrol;

import java.io.IOException;
import java.nio.ByteBuffer;

public final class FramePixels {
    private FramePixels() {}

    public static byte[] compactRgba(ByteBuffer source, int width, int height, int rowStride, int pixelStride)
            throws IOException {
        if (pixelStride != 4 || width <= 0 || height <= 0 || width > 1920 || height > 1920
                || rowStride < width * 4) {
            throw new IOException("지원하지 않는 화면 프레임 형식");
        }
        int sourceStart = source.position();
        long required = sourceStart + (long) (height - 1) * rowStride + (long) width * 4;
        if (required > source.limit()) throw new IOException("화면 프레임 데이터가 잘렸습니다.");
        byte[] compact = new byte[Math.multiplyExact(Math.multiplyExact(width, height), 4)];
        for (int y = 0; y < height; y++) {
            source.position(sourceStart + y * rowStride);
            source.get(compact, y * width * 4, width * 4);
        }
        return compact;
    }
}
