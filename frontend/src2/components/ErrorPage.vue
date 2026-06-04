<script setup lang="ts">
import { Button } from 'frappe-ui'
import { AlertTriangle, FileQuestion } from 'lucide-vue-next'
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { __ } from '../translation'
import { getErrorMessage } from '../helpers'

const props = defineProps<{
	error?: any
	title?: string
	message?: string
}>()

const router = useRouter()

const isNotFound = computed(() => {
	const text = String(props.error?.exc || props.error?.message || props.error || '')
	return text.includes('DoesNotExistError') || text.includes('404')
})

const resolvedTitle = computed(() => {
	if (props.title) return props.title
	return isNotFound.value ? __('Not found') : __('Something went wrong')
})

const resolvedMessage = computed(() => {
	if (props.message) return props.message
	return isNotFound.value
		? __("The page you're looking for doesn't exist or may have been deleted.")
		: getErrorMessage(props.error) || __('An unexpected error occurred.')
})

function goHome() {
	router.push('/')
}
</script>

<template>
	<div class="flex h-full w-full items-center justify-center bg-white p-6">
		<div class="flex max-w-md flex-col items-center gap-5 text-center">
			<component
				:is="isNotFound ? FileQuestion : AlertTriangle"
				class="h-14 w-14 text-gray-300"
				stroke-width="1"
			/>
			<div class="space-y-1.5">
				<h1 class="text-lg font-semibold text-gray-800">{{ resolvedTitle }}</h1>
				<p class="text-sm text-gray-500">{{ resolvedMessage }}</p>
			</div>
			<div class="flex items-center gap-2">
				<Button variant="outline" @click="goHome">{{ __('Go to Home') }}</Button>
			</div>
			<details v-if="error" class="w-full text-left">
				<summary class="cursor-pointer text-xs text-gray-400 hover:text-gray-600">
					{{ __('Show error details') }}
				</summary>
				<pre
					class="mt-2 max-h-48 overflow-auto rounded bg-gray-50 p-3 text-xs whitespace-pre-wrap break-all text-gray-500"
					>{{ getErrorMessage(error) }}</pre
				>
			</details>
		</div>
	</div>
</template>
