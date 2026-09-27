$(document).ready(function () {

    let cart = [];

    // ============================================================
    // GST RATE
    // ============================================================

    const GST_RATE = 0.18;


    // ============================================================
    // UPDATE CART DISPLAY
    // ============================================================

    function updateCart() {

        $('#cartItems').empty();

        let subtotal = 0;

        cart.forEach((item, index) => {

            // Recalculate item total
            item.total = item.price * item.quantity;

            subtotal += item.total;

            $('#cartItems').append(`
                <tr>

                    <!-- Medicine Name -->
                    <td>
                        ${escapeHtml(item.name)}
                    </td>

                    <!-- Price -->
                    <td>
                        ₹${item.price.toFixed(2)}
                    </td>

                    <!-- Quantity -->
                    <td>
                        <div
                            class="input-group input-group-sm"
                            style="width: 120px;"
                        >

                            <button
                                class="btn btn-outline-secondary minus-item"
                                type="button"
                                data-index="${index}"
                            >
                                -
                            </button>

                            <input
                                type="number"
                                class="form-control text-center quantity-input"
                                value="${item.quantity}"
                                min="1"
                                max="${item.stock}"
                                data-index="${index}"
                            >

                            <button
                                class="btn btn-outline-secondary plus-item"
                                type="button"
                                data-index="${index}"
                            >
                                +
                            </button>

                        </div>
                    </td>

                    <!-- MFG Date -->
                    <td>
                        ${escapeHtml(item.mfg_date || 'N/A')}
                    </td>

                    <!-- Expiry Date -->
                    <td>
                        ${escapeHtml(item.expiry_date || 'N/A')}
                    </td>

                    <!-- Total -->
                    <td>
                        ₹${item.total.toFixed(2)}
                    </td>

                    <!-- Action -->
                    <td>
                        <button
                            type="button"
                            class="btn btn-sm btn-danger remove-item"
                            data-index="${index}"
                            title="Remove"
                        >
                            <i class="bi bi-trash"></i>
                        </button>
                    </td>

                </tr>
            `);
        });


        // ========================================================
        // DISCOUNT
        // ========================================================

        let discount = parseFloat(
            $('#discount').val()
        );

        if (
            isNaN(discount) ||
            discount < 0
        ) {
            discount = 0;
        }


        // Discount cannot be greater than subtotal
        if (discount > subtotal) {

            discount = subtotal;

            $('#discount').val(
                discount.toFixed(2)
            );
        }


        // ========================================================
        // GST CALCULATION
        // ========================================================

        const taxableAmount =
            subtotal - discount;

        const gst =
            taxableAmount * GST_RATE;


        // ========================================================
        // GRAND TOTAL
        // ========================================================

        const grandTotal =
            taxableAmount + gst;


        // ========================================================
        // UPDATE SUMMARY
        // ========================================================

        $('#subtotal').text(
            `₹${subtotal.toFixed(2)}`
        );

        $('#displayDiscount').text(
            `₹${discount.toFixed(2)}`
        );

        $('#displayTax').text(
            `₹${gst.toFixed(2)}`
        );

        $('#grandTotal').text(
            `₹${grandTotal.toFixed(2)}`
        );


        // ========================================================
        // HIDDEN GST FIELD
        // ========================================================

        $('#tax').val(
            gst.toFixed(2)
        );


        // ========================================================
        // HIDDEN CART FIELD
        // ========================================================

        $('#cart_items').val(
            JSON.stringify(cart)
        );
    }


    // ============================================================
    // ESCAPE HTML
    // ============================================================

    function escapeHtml(text) {

        if (
            text === null ||
            text === undefined
        ) {
            return '';
        }

        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }


    // ============================================================
    // CHECK EXPIRY DATE
    // ============================================================

    function isExpired(expiryDate) {

        if (
            !expiryDate ||
            expiryDate === 'N/A'
        ) {
            return false;
        }


        /*
         * Expected format:
         * DD-MM-YYYY
         */

        const parts =
            String(expiryDate).split('-');


        if (parts.length !== 3) {
            return false;
        }


        const day =
            parseInt(parts[0], 10);

        const month =
            parseInt(parts[1], 10) - 1;

        const year =
            parseInt(parts[2], 10);


        if (
            isNaN(day) ||
            isNaN(month) ||
            isNaN(year)
        ) {
            return false;
        }


        const expiry = new Date(
            year,
            month,
            day
        );


        expiry.setHours(
            0,
            0,
            0,
            0
        );


        const today = new Date();

        today.setHours(
            0,
            0,
            0,
            0
        );


        /*
         * Today is also considered expired.
         */

        return expiry <= today;
    }


    // ============================================================
    // ADD MEDICINE TO CART
    // ============================================================

    $(document).on(
        'click',
        '.add-to-cart',
        function () {

            const medicineId =
                String(
                    $(this).attr('data-id')
                );


            const medicineName =
                String(
                    $(this).attr('data-name')
                );


            const medicinePrice =
                parseFloat(
                    $(this).attr('data-price')
                );


            const medicineStock =
                parseInt(
                    $(this).attr('data-stock'),
                    10
                );


            // ====================================================
            // MFG DATE
            // ====================================================

            const medicineMfg =
                String(
                    $(this).attr('data-mfg') ||
                    'N/A'
                );


            // ====================================================
            // EXPIRY DATE
            // ====================================================

            const medicineExpiry =
                String(
                    $(this).attr('data-expiry') ||
                    'N/A'
                );


            // ====================================================
            // VALIDATE PRICE
            // ====================================================

            if (
                isNaN(medicinePrice)
            ) {

                alert(
                    'Invalid medicine price!'
                );

                return;
            }


            // ====================================================
            // VALIDATE STOCK
            // ====================================================

            if (
                isNaN(medicineStock) ||
                medicineStock <= 0
            ) {

                alert(
                    'This medicine is out of stock!'
                );

                return;
            }


            // ====================================================
            // CHECK EXPIRY
            // ====================================================

            if (
                isExpired(medicineExpiry)
            ) {

                alert(
                    'This medicine is expired and cannot be added to the cart!'
                );

                return;
            }


            // ====================================================
            // CHECK EXISTING MEDICINE
            // ====================================================

            const existingItem =
                cart.find(
                    item =>
                        String(item.id) ===
                        medicineId
                );


            if (existingItem) {

                // Check stock

                if (
                    existingItem.quantity <
                    existingItem.stock
                ) {

                    existingItem.quantity += 1;

                    existingItem.total =
                        existingItem.price *
                        existingItem.quantity;

                } else {

                    alert(
                        'Cannot add more than available stock!'
                    );

                    return;
                }

            } else {

                // =================================================
                // ADD NEW MEDICINE
                // =================================================

                cart.push({

                    id: medicineId,

                    name: medicineName,

                    price: medicinePrice,

                    quantity: 1,

                    total: medicinePrice,

                    stock: medicineStock,

                    // MFG DATE
                    mfg_date: medicineMfg,

                    // EXPIRY DATE
                    expiry_date: medicineExpiry
                });
            }


            updateCart();
        }
    );


    // ============================================================
    // MINUS QUANTITY
    // ============================================================

    $(document).on(
        'click',
        '.minus-item',
        function () {

            const index =
                parseInt(
                    $(this).attr('data-index'),
                    10
                );


            if (!cart[index]) {
                return;
            }


            if (
                cart[index].quantity > 1
            ) {

                cart[index].quantity -= 1;

                cart[index].total =
                    cart[index].price *
                    cart[index].quantity;

                updateCart();
            }
        }
    );


    // ============================================================
    // PLUS QUANTITY
    // ============================================================

    $(document).on(
        'click',
        '.plus-item',
        function () {

            const index =
                parseInt(
                    $(this).attr('data-index'),
                    10
                );


            if (!cart[index]) {
                return;
            }


            // Check expiry again

            if (
                isExpired(
                    cart[index].expiry_date
                )
            ) {

                alert(
                    'This medicine is expired and cannot be billed!'
                );

                return;
            }


            if (
                cart[index].quantity <
                cart[index].stock
            ) {

                cart[index].quantity += 1;

                cart[index].total =
                    cart[index].price *
                    cart[index].quantity;

                updateCart();

            } else {

                alert(
                    'Cannot add more than available stock!'
                );
            }
        }
    );


    // ============================================================
    // MANUAL QUANTITY INPUT
    // ============================================================

    $(document).on(
        'change',
        '.quantity-input',
        function () {

            const index =
                parseInt(
                    $(this).attr('data-index'),
                    10
                );


            if (!cart[index]) {
                return;
            }


            let newQuantity =
                parseInt(
                    $(this).val(),
                    10
                );


            if (
                !isNaN(newQuantity) &&
                newQuantity >= 1 &&
                newQuantity <=
                cart[index].stock
            ) {

                cart[index].quantity =
                    newQuantity;

                cart[index].total =
                    cart[index].price *
                    newQuantity;

                updateCart();

            } else {

                $(this).val(
                    cart[index].quantity
                );

                alert(
                    'Quantity must be between 1 and available stock!'
                );
            }
        }
    );


    // ============================================================
    // REMOVE MEDICINE
    // ============================================================

    $(document).on(
        'click',
        '.remove-item',
        function () {

            const index =
                parseInt(
                    $(this).attr('data-index'),
                    10
                );


            if (!isNaN(index)) {

                cart.splice(
                    index,
                    1
                );

                updateCart();
            }
        }
    );


    // ============================================================
    // CLEAR CART
    // ============================================================

    $('#clearCart').on(
        'click',
        function () {

            if (
                cart.length === 0
            ) {
                return;
            }


            if (
                confirm(
                    'Are you sure you want to clear the cart?'
                )
            ) {

                cart = [];

                updateCart();
            }
        }
    );


    // ============================================================
    // DISCOUNT LIVE CALCULATION
    // ============================================================

    $('#discount').on(
        'input',
        function () {

            let value =
                parseFloat(
                    $(this).val()
                );


            if (
                isNaN(value) ||
                value < 0
            ) {

                $(this).val(0);
            }


            updateCart();
        }
    );


    // ============================================================
    // MEDICINE SEARCH
    // ============================================================

    $('#medicineSearch').on(
        'input',
        function () {

            const searchText =
                String(
                    $(this).val()
                )
                .trim()
                .toLowerCase();


            const medicineItems =
                $('.medicine-item');


            let visibleCount = 0;


            medicineItems.each(
                function () {

                    const medicineName =
                        String(
                            $(this).attr(
                                'data-name'
                            ) || ''
                        )
                        .toLowerCase();


                    if (
                        medicineName.includes(
                            searchText
                        )
                    ) {

                        $(this).show();

                        visibleCount++;

                    } else {

                        $(this).hide();
                    }
                }
            );


            if (
                visibleCount === 0
            ) {

                $('#noSearchResults')
                    .show();

            } else {

                $('#noSearchResults')
                    .hide();
            }
        }
    );


    // ============================================================
    // FORM SUBMISSION
    // ============================================================
    //
    // IMPORTANT:
    // Your billing.html uses:
    // id="billingForm"
    //
    // So use #billingForm here.
    // ============================================================

    $('#billingForm').on(
        'submit',
        function (e) {

            // ====================================================
            // CHECK CART
            // ====================================================

            if (
                cart.length === 0
            ) {

                e.preventDefault();

                alert(
                    'Please add at least one medicine to the bill!'
                );

                return;
            }


            // ====================================================
            // CHECK EXPIRED MEDICINES
            // ====================================================

            const hasExpiredMedicines =
                cart.some(
                    item =>
                        isExpired(
                            item.expiry_date
                        )
                );


            if (
                hasExpiredMedicines
            ) {

                e.preventDefault();

                alert(
                    'Cannot generate bill. There are expired medicines in the cart!'
                );

                return;
            }


            // ====================================================
            // CHECK QUANTITY
            // ====================================================

            for (
                let i = 0;
                i < cart.length;
                i++
            ) {

                const item =
                    cart[i];


                if (
                    item.quantity <= 0
                ) {

                    e.preventDefault();

                    alert(
                        `Invalid quantity for ${item.name}!`
                    );

                    return;
                }


                if (
                    item.quantity >
                    item.stock
                ) {

                    e.preventDefault();

                    alert(
                        `Quantity exceeds available stock for ${item.name}!`
                    );

                    return;
                }
            }


            // ====================================================
            // UPDATE CART
            // ====================================================

            updateCart();


            // ====================================================
            // COPY PRESCRIPTION NOTES
            // ====================================================

            const prescriptionNotes =
                $('#prescription').val() || '';


            $('#prescription_notes').val(
                prescriptionNotes
            );


            // ====================================================
            // FINAL CART JSON
            // ====================================================

            $('#cart_items').val(
                JSON.stringify(cart)
            );
        }
    );


    // ============================================================
    // INITIAL CART UPDATE
    // ============================================================

    updateCart();

});