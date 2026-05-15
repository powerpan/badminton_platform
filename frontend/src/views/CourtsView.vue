<template>
  <section class="page-header">
    <p class="eyebrow">用户端</p>
    <h1>场地预约</h1>
    <p>后续在这里接入场地列表、日期筛选、时间段状态和提交预约流程。</p>
  </section>

  <section class="panel">
    <h2>开发顺序</h2>
    <ol class="task-list">
      <li>读取启用场地列表。</li>
      <li>按日期查询时间段状态。</li>
      <li>提交预约时使用 Redis 锁防止重复占用。</li>
      <li>预约成功后刷新我的预约和时间段状态。</li>
    </ol>
  </section>
</template>
