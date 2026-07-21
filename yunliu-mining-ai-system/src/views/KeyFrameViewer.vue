<template>
  <div>
    <h2>关键帧查看</h2>
    <div v-if="loading">加载中...</div> <!-- 加载状态 -->
    <div v-else-if="keyframes.length === 0">暂无关键帧数据</div> <!-- 无数据状态 -->
    <el-carousel v-else indicator-position="outside" class="keyframe-carousel"> <!-- 显示关键帧 -->
      <el-carousel-item v-for="(keyframe, index) in keyframes" :key="index">
        <div class="carousel-item-content">
          <!-- 显示通道信息 -->
          <div class="keyframe-info">通道 {{ keyframe.channel + 1 }} - {{ keyframe.timestamp }}</div>
          <img
            :src="getFullKeyFramePath(keyframe.keyframe_path)"
            alt="关键帧"
            class="keyframe-img"
          />
        </div>
      </el-carousel-item>
    </el-carousel>
  </div>
</template>

<script>
import axios from "axios";
import dayjs from "dayjs"; // 导入 dayjs 用于格式化时间

export default {
  data() {
    return {
      keyframes: [], // 存储从后端提取的关键帧数据 (包含路径和通道)
      loading: true, // 加载状态
    };
  },
  methods: {
    async fetchKeyFrames() {
      try {
        // 从后端获取报警记录数据
        const response = await axios.get("http://127.0.0.1:8000/api/alarms");
        // 提取所有报警记录中的 keyframe_path, channel 和 timestamp 字段
        this.keyframes = response.data
          .filter(alarm => alarm.keyframe_path) // 过滤掉没有关键帧的记录
          .map((alarm) => ({
            keyframe_path: alarm.keyframe_path,
            channel: alarm.channel,
            timestamp: dayjs(alarm.timestamp).format("YYYY-MM-DD HH:mm:ss") // 格式化时间
          }));
      } catch (error) {
        console.error("获取关键帧数据失败：", error);
        this.keyframes = [];
      } finally {
        this.loading = false; // 加载完成
      }
    },
    getFullKeyFramePath(keyframePath) {
      // 拼接完整路径
      return `http://127.0.0.1:8000${keyframePath}`;
    },
  },
  mounted() {
    this.fetchKeyFrames(); // 组件挂载时获取关键帧数据
  },
};
</script>

<style scoped>
.keyframe-carousel {
  width: 80%; /* 轮播图宽度 */
  height: 500px; /* 轮播图高度 */
  margin: 20px auto; /* 居中显示 */
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1); /* 添加阴影效果 */
  border-radius: 8px; /* 添加圆角 */
  overflow: hidden; /* 隐藏超出圆角的部分 */
}

/* 调整轮播图项内部内容的布局 */
.carousel-item-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%; /* 使内容填充整个轮播图项 */
  padding: 20px; /* 添加内边距 */
  box-sizing: border-box; /* 包含内边距在宽度内 */
}


.el-carousel__item h3 {
  color: #475669;
  font-size: 18px;
  opacity: 0.75;
  line-height: 300px;
  margin: 0;
  text-align: center;
}

.keyframe-img {
  max-width: 100%; /* 图片最大宽度为其父容器的100% */
  max-height: 100%; /* 图片最大高度为其父容器的100% */
  object-fit: contain; /* 保持图片比例并适应容器 */
  display: block;
  border-radius: 4px; /* 图片圆角 */
}

.keyframe-info {
  text-align: center;
  margin-bottom: 15px; /* 增加信息与图片之间的间距 */
  font-size: 18px; /* 稍微增大字体 */
  color: #555; /* 调整字体颜色 */
  font-weight: bold; /* 加粗字体 */
}

/* 可以根据需要调整轮播图指示器和箭头的样式 */
/* 例如： */
/*
.keyframe-carousel /deep/ .el-carousel__indicator button {
  background-color: #409EFF;
}
.keyframe-carousel /deep/ .el-carousel__arrow {
  background-color: rgba(0, 0, 0, 0.5);
}
*/
</style>
