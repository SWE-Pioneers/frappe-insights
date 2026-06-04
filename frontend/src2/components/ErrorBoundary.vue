<script setup lang="ts">
import { onErrorCaptured, shallowRef, watch } from 'vue'
import { useRoute } from 'vue-router'
import ErrorPage from './ErrorPage.vue'

const error = shallowRef<any>(null)
const route = useRoute()

onErrorCaptured((err) => {
	error.value = err
	// stop propagation — we've surfaced it via the fallback page
	return false
})

// recover when the user navigates away from the broken route
watch(
	() => route.fullPath,
	() => {
		error.value = null
	},
)
</script>

<template>
	<ErrorPage v-if="error" :error="error" />
	<slot v-else />
</template>
