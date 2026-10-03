package com.zhk.shelfsense.scan

data class PriceCandidate(val text: String, val heightPx: Int, val confidence: Float)

data class ParsedPrice(val cents: Int, val rawText: String, val confidence: Float)

object PriceParser {

    private val decimalPrice = Regex("""(?<!\d)\$?\s?(\d{1,4})[.,](\d{2})(?!\d)""")

    // Shelf labels often print cents as superscript ("$3⁴⁹"), which OCR reads as "$349".
    private val superscriptCents = Regex("""\$\s?(\d{3,4})(?!\d)""")

    fun parseCents(text: String): Int? {
        decimalPrice.find(text)?.let { match ->
            val (dollars, cents) = match.destructured
            return dollars.toInt() * 100 + cents.toInt()
        }
        superscriptCents.find(text)?.let { match ->
            return match.groupValues[1].toInt()
        }
        return null
    }

    /** The shelf price is the physically largest price-like text on the label, not the unit price. */
    fun bestPrice(candidates: List<PriceCandidate>): ParsedPrice? =
        candidates
            .mapNotNull { candidate ->
                parseCents(candidate.text)?.let { cents -> candidate to cents }
            }
            .maxByOrNull { (candidate, _) -> candidate.heightPx }
            ?.let { (candidate, cents) -> ParsedPrice(cents, candidate.text, candidate.confidence) }
}
