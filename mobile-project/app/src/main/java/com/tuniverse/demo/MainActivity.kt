package com.tuniverse.demo

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.tuniverse.demo.databinding.ActivityMainBinding
import com.tuniverse.demo.data.repo.TuniverseRepo
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MainActivity : AppCompatActivity() {
    private lateinit var binding: ActivityMainBinding
    private val repo = TuniverseRepo()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.btnGenerate.setOnClickListener {
            val userId = binding.userIdInput.text?.toString()?.ifBlank { "demo_user" } ?: "demo_user"
            binding.resultText.text = "Loading…"
            CoroutineScope(Dispatchers.IO).launch {
                val res = repo.fetchPassport(userId)
                withContext(Dispatchers.Main) {
                    res.fold(
                        onSuccess = { data ->
                            val sb = StringBuilder()
                            sb.appendLine("User: ${data.user_id}")
                            sb.appendLine("Total artists: ${data.total_artists}")
                            sb.appendLine("Countries:")
                            data.country_counts.forEach { (c, n) -> sb.appendLine("• $c: $n") }
                            sb.appendLine("Regions:")
                            data.region_percentages.forEach { (r, p) -> sb.appendLine("• $r: ${(p * 100).toInt()}%") }
                            data.share_link?.let { sb.appendLine("Share: $it") }
                            binding.resultText.text = sb.toString()
                        },
                        onFailure = { e ->
                            binding.resultText.text = "Error: ${e.message ?: e.javaClass.simpleName}"
                        }
                    )
                }
            }
        }
    }
}
