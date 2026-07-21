<template>
  <div class="video-grid">
    <div v-for="channel in 8" :key="channel-1" class="video-cell">
      <!-- <h3>通道 {{ channel }}</h3> -->
      <div class="upload-container">
        <el-upload
          class="upload-demo"
          :action="`http://127.0.0.1:8001/api/video/upload/${channel-1}`"
          :on-success="(res) => handleUploadSuccess(res, channel-1)"
          :on-error="handleUploadError"
          :auto-upload="true"
          accept=".mp4,.avi,.mkv"
          :before-upload="beforeUpload"
        >
          <el-button size="small" type="primary">点击上传视频文件</el-button>
        </el-upload>
      </div>

      <div v-if="videoUploaded[channel-1]" class="video-container">
        <img
          :src="getVideoStreamUrl(channel-1)"
          :alt="`Video Stream ${channel}`"
          class="video-stream"
        />
      </div>
       <div v-else class="video-placeholder">
         <p>通道 {{ channel }} 视频未上传</p>
       </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'VideoGrid', // 添加这一行
  data() {
    return {
      videoUploaded: [false, false, false, false, false, false, false, false],
    };
  },
  methods: {
    handleUploadSuccess(response, channel) {
      console.log(`通道 ${channel + 1} 视频上传成功`, response);
      this.videoUploaded[channel] = true; 
      this.$message.success(`通道 ${channel + 1} 视频上传成功`);
    },
    handleUploadError(err) {
      console.error("上传失败:", err);
      this.$message.error("视频上传失败");
    },
     beforeUpload(file) {
      const maxSize = 500 * 1024 * 1024; // 500MB
      if (file.size > maxSize) {
        this.$message.error('上传视频大小不能超过 500MB!');
        return false;
      }
      return true;
    },
    getVideoStreamUrl(channel) {
      // 添加一个随机参数防止浏览器缓存
      return `http://127.0.0.1:8001/api/video/video_stream/${channel}?t=${Date.now()}`;
    },
  },
};
</script>

<style scoped>
.video-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
  padding: 20px;
}

.video-cell {
  border: 1px solid #ddd;
  background-color: #fff;
  padding: 10px;
  border-radius: 4px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.upload-container {
}

.video-container {
  margin-top: 10px;
  width: 100%; /* 确保视频容器宽度填充单元格 */
  text-align: center;
}

.video-stream {
  width: 100%;
  height: auto;
  border-radius: 4px;
}

.video-placeholder {
    width: 100%;
    height: 300px; /* 与视频流高度一致 */
    background-color: #f0f0f0;
    display: flex;
    justify-content: center;
    align-items: center;
    color: #666;
    border-radius: 4px;
}
</style>