<script setup>
import { inject } from 'vue'
const dashboard = inject('dashboard')
</script>

<template>
	<div class="flex flex-1 flex-col items-center justify-center space-y-1">
		<div class="text-base font-light text-gray-600">
			{{
				!dashboard.editing ? __("You haven't added any charts.") : __('Drag and drop charts here.')
			}}
		</div>
		<div
			v-if="!dashboard.editing"
			class="cursor-pointer text-sm font-light text-blue-500 hover:underline"
			@click="dashboard.edit"
		>
			{{ __('Add a chart') }}
		</div>
	</div>
</template>
