package com.remotecontrol;

import org.junit.Test;
import java.io.IOException;
import java.nio.ByteBuffer;
import static org.junit.Assert.*;

public class FramePixelsTest {
    @Test public void removesRowPaddingWithoutTruncatingLastRow() throws Exception {
        ByteBuffer padded = ByteBuffer.wrap(new byte[]{
                1, 2, 3, 4, 5, 6, 7, 8, 90, 91, 92, 93,
                9, 10, 11, 12, 13, 14, 15, 16
        });

        assertArrayEquals(new byte[]{
                1, 2, 3, 4, 5, 6, 7, 8,
                9, 10, 11, 12, 13, 14, 15, 16
        }, FramePixels.compactRgba(padded, 2, 2, 12, 4));
    }

    @Test public void rejectsTruncatedImagePlane() throws Exception {
        try {
            FramePixels.compactRgba(ByteBuffer.wrap(new byte[15]), 2, 2, 12, 4);
            fail("truncated frame accepted");
        } catch (IOException expected) {
            assertEquals("화면 프레임 데이터가 잘렸습니다.", expected.getMessage());
        }
    }
}
