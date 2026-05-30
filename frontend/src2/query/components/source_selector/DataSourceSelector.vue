<script setup>
import { Combobox } from 'frappe-ui'
import { Database } from 'lucide-vue-next'
import { computed } from 'vue'
import useDataSourceStore from '../../../data_source/data_source'

const currentSourceName = defineModel()
const props = defineProps({
	placeholder: {
		type: String,
		default: 'Data source',
	},
})

const dataSourceStore = useDataSourceStore()
const dataSourceOptions = computed(() => {
	return dataSourceStore.sources.map((source) => ({
		label: source.title,
		value: source.name,
	}))
})
</script>

<template>
	<Combobox
		class="!w-fit"
		trigger="button"
		variant="outline"
		:options="dataSourceOptions"
		v-model="currentSourceName"
		:placeholder="placeholder"
	>
		<template #prefix>
			<Database class="h-3.5 w-3.5 flex-shrink-0" stroke-width="1.5" />
		</template>
	</Combobox>
</template>
