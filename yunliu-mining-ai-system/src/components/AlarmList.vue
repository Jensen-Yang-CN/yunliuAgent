<template>
  <div>
    <h2>报警记录</h2>
    <div class="filter-container">
      <!-- <label for="channel-select">选择通道:</label> -->
      <el-select id="channel-select" v-model="selectedChannel" placeholder="请选择">
        <el-option label="所有通道" :value="-1"></el-option>
        <el-option v-for="i in 4" :key="i-1" :label="`通道 ${i}`" :value="i-1"></el-option>
      </el-select>
    </div>

    <el-table :data="filteredAlarms" border>
      <el-table-column
        prop="timestamp"
        label="报警时间"
        width="200"
        :formatter="formatTimestamp"
       />
       <!-- 添加通道列 -->
       <el-table-column prop="channel" label="通道" width="80">
         <template #default="scope">
           通道 {{ scope.row.channel + 1 }}
         </template>
       </el-table-column>
      <el-table-column prop="description" label="报警描述" />
      <el-table-column label="关键帧">
        <template #default="scope">
          <img
            v-if="scope.row.keyframe_path"
            :src="getFullKeyFramePath(scope.row.keyframe_path)"
            alt="关键帧"
            class="keyframe-img"
            @click="viewKeyFrame(scope.row.keyframe_path)"
          />
           <span v-else>无关键帧</span>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" width="50%" title="关键帧">
      <img :src="selectedKeyFrame" alt="关键帧" class="dialog-keyframe-img" />
    </el-dialog>
  </div>
</template>

<script>
import axios from "axios";
import dayjs from "dayjs";

export default {
  data() {
    return {
      alarms: [],
      selectedChannel: -1, // -1 表示所有通道
      dialogVisible: false,
      selectedKeyFrame: "",
    };
  },
  computed: {
    filteredAlarms() {
      let result = this.alarms;
      if (this.selectedChannel !== -1) {
        // 过滤指定通道的报警
        result = this.alarms.filter(alarm => alarm.channel === this.selectedChannel);
      }
      // 按时间戳降序排序
      return result.sort((a, b) => {
        // 将时间字符串转换为 Date 对象或时间戳进行比较
        const timeA = new Date(a.timestamp).getTime();
        const timeB = new Date(b.timestamp).getTime();
        return timeB - timeA; // 降序排列
      });
    }
  },
  methods: {
    async fetchAlarms() {
      try {
        // 从后端获取所有报警记录数据
        const response = await axios.get("http://127.0.0.1:8000/api/alarms");
        this.alarms = response.data;
      } catch (error) {
        console.error("获取报警记录数据失败：", error);
        this.alarms = [];
      }
    },
    formatTimestamp(row, column, cellValue) {
      // 使用 dayjs 格式化时间
      return dayjs(cellValue).format("YYYY-MM-DD HH:mm:ss");
    },
    viewKeyFrame(keyframePath) {
      // 显示选中的关键帧图片
      this.selectedKeyFrame = this.getFullKeyFramePath(keyframePath);
      this.dialogVisible = true;
    },
     getFullKeyFramePath(keyframePath) {
      // 拼接完整路径
      return `http://127.0.0.1:8000${keyframePath}`;
    },
  },
  mounted() {
    this.fetchAlarms(); // 组件挂载时获取报警记录
  },
};
</script>

<style scoped>
.filter-container {
  margin-bottom: 20px;
  display: flex;
  align-items: center;
}

.filter-container label {
  margin-right: 10px;
}

.keyframe-img {
  width: 80px; /* 列表中关键帧缩略图大小 */
  height: auto;
  cursor: pointer; /* 鼠标悬停时显示手型 */
  border-radius: 4px;
}

.dialog-keyframe-img {
  width: 100%; /* 弹窗中关键帧图片大小 */
  height: auto;
  display: block; /* 避免底部空白 */
}
</style>
